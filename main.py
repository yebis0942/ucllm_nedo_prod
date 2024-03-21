import argparse
import itertools
import os
import tempfile
from shlex import quote
from subprocess import run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", help="origin repository", required=True)
    parser.add_argument("--committer-name", required=True)
    parser.add_argument("--committer-email", required=True)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as dir:
        clone_repository(args.repository, dir)

        os.chdir(dir)
        make_linear_commits(args.committer_name, args.committer_email)
        regenerate_tags()

        print("Repository cloned to", dir)

        input()


def clone_repository(repository, dir):
    run(
        [
            "git",
            "clone",
            repository,
            dir,
        ],
        check=True,
    )


def make_linear_commits(committer_name, committer_email):
    # 空のブランチを作成する
    run(["git", "switch", "--orphan", "linearized"], check=True)

    tags = get_tags()

    # 最初のタグの内容をコミットする
    run(
        ["git", "cherry-pick", tags[0]],
        check=True,
        env=get_commit_env(tags[0], committer_name, committer_email),
    )

    # 2つ目以降のタグの内容をコミットする
    for current_tag, next_tag in itertools.pairwise(tags):
        run(
            "git diff --patch --binary {} {} | git apply -".format(
                quote(current_tag), quote(next_tag)
            ),
            check=True,
            shell=True,
        )
        run(["git", "add", "-A"], check=True)

        run(
            ["git", "commit", "-m", next_tag],
            check=True,
            env=get_commit_env(next_tag, committer_name, committer_email),
        )


def regenerate_tags():
    # ここまでに作成したコミットIDを古い順に取得する
    commits = (
        run(
            ["git", "log", "-s", "--format=%H", "--reverse"],
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .splitlines()
    )

    tags = get_tags()

    # タグを打ち直す
    for tag, commit in zip(tags, commits, strict=True):
        run(
            ["git", "tag", "-d", tag],
            check=True,
        )
        run(
            ["git", "tag", tag, commit],
            check=True,
        )


def get_tags():
    return (
        run(["git", "tag"], check=True, capture_output=True)
        .stdout.decode("utf-8")
        .splitlines()
    )


def get_commit_env(tag, committer_name, committer_email):
    [author_name, author_email, author_date] = (
        run(
            # author_name, author_email, author_dateを改行区切りで出力する
            ["git", "show", "-s", "--pretty='%an%n%ae%n%aI'", tag],
            check=True,
            capture_output=True,
        )
        .stdout.decode("utf-8")
        .splitlines()
    )

    return {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": author_email,
        "GIT_AUTHOR_DATE": author_date,
        "GIT_COMMITTER_NAME": committer_name,
        "GIT_COMMITTER_EMAIL": committer_email,
        # コミットIDが実行時刻によって変わらないように固定値を設定している
        "GIT_COMMITTER_DATE": author_date,
    }


if __name__ == "__main__":
    main()
