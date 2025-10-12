import json
import os
import pathlib
import re
import base64
import time

from datetime import datetime
from typing import Optional

from furl import furl
from github import Github, Auth, ContentFile, Issue

def get_token() -> str:
    if pathlib.Path("TOKEN").exists():
        return open("TOKEN").read().strip()

    return os.environ["BFG_PAT_GITHUB"]

auth = Auth.Token(get_token())
gh = Github(auth=auth)

REPO = gh.get_organization("inflated-goboscript").get_repo("gtp")

class GTP:
    @property
    def raw_data(self) -> str:
        raw = REPO.get_contents("gtp.json")
        assert isinstance(raw, ContentFile.ContentFile)
        assert raw.encoding == "base64"

        return base64.b64decode(raw.content).decode()

    @raw_data.setter
    def raw_data(self, value: str):
        REPO.update_file("gtp.json", "update gtp.raw_data", value, REPO.get_contents("gtp.json").sha)

    @property
    def data(self) -> dict[str, dict[str, str]]:
        return json.loads(self.raw_data)

    @data.setter
    def data(self, value: dict[str, dict[str, str]]):
        self.raw_data = json.dumps(value)

    def __setitem__(self, key: str, value: dict[str, str]):
        data = self.data
        data[key] = value
        self.data = data

gtp = GTP()

def resolve_registrations():
    for issue in REPO.get_issues(
            state="open",
            labels=["register"]
    ):
        print(f"Found open issue with `register` tag: {issue.url}")

        body = issue.body

        if re.match(''
                    r"### Name\n\n"
                    r"[a-zA-Z0-9_-]+\n\n"
                    r"### URL\n\n"
                    r"https?://github\.com(/([a-zA-Z0-9._-]+)){2}/?", body):
            lines = body.splitlines()

            assert len(lines) == 7, f"Invalid body: {lines}"

            name = lines[2].lower()
            url = furl(lines[6].lower())

            register_package(name, url, issue)

        else:
            print("Invalid syntax")

            issue.create_comment("""\
This issue syntax is invalid.
- The name can only be made up of a-z, A-Z, underscores or dashes.
- The URL has to be a valid **GitHub** URL, to the root of the repository.\
""")
            issue.edit(state="closed",
                       state_reason="not_planned")

def find(data: dict[str, dict[str, str]], key: str, value: str, default=None) -> Optional[str]:
     for k, v in data.items():
         if v.get(key, default) == value:
             return k

     return None

def register_package(name: str, url: furl, issue: Issue.Issue):
    message = ""
    def mlog(msg, end: str = '\n'):
        nonlocal message
        print(msg, end=end)
        message += str(msg) + end

    mlog(f"- Registering `{name!r}` for `{url}`")

    data = gtp.data

    url_str = parse_url(url)
    mlog(f"- Parsed furl as `{url_str}`")

    if existing_url := data.get(name):
        if existing_url == url_str:
            mlog("## This was already registered!")

            issue.create_comment(message)
            issue.edit(state="closed", state_reason="duplicate")
            return

        mlog(f"## Oh no, name already taken: `{existing_url}`")

        issue.create_comment(message)
        issue.edit(state="closed", state_reason="not_planned")
        return

    if existing_name := find(data, "url", url_str):
        mlog(f"## Repo already registered as `{existing_name}`")

        issue.create_comment(message)
        issue.edit(state="closed", state_reason="not_planned")
        return

    gtp[name] = {"url": url_str}
    mlog("## Added!! See [gtp.json](https://github.com/inflated-goboscript/gtp/blob/main/gtp.json)!")

    issue.create_comment(message)
    issue.edit(state="closed")


def parse_url(url: furl) -> str:
    return "https://github.com/" + '/'.join(url.path.segments)


def main():
    while True:
        print(f"Checking for registrations... {datetime.now()}")
        resolve_registrations()
        time.sleep(60)

if __name__ == '__main__':
    main()
