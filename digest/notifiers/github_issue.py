"""GitHub 이슈로 발행.

Actions 안에서는 GITHUB_TOKEN / GITHUB_REPOSITORY 가 자동으로 주어진다.
로컬에서는 GITHUB_TOKEN(또는 GH_TOKEN)과 GITHUB_REPOSITORY(owner/repo)를 직접 설정한다.
DIGEST_ISSUE_LABEL 로 라벨을 바꿀 수 있다(기본: digest).
"""
from __future__ import annotations

import os

import requests

NAME = "github_issue"
API = "https://api.github.com"


def _token() -> str | None:
    return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")


def available() -> tuple[bool, str]:
    if not _token():
        return False, "GITHUB_TOKEN 이 설정되지 않았습니다"
    if not os.environ.get("GITHUB_REPOSITORY"):
        return False, "GITHUB_REPOSITORY(owner/repo)가 설정되지 않았습니다"
    return True, ""


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _ensure_label(repo: str, label: str) -> None:
    r = requests.get(f"{API}/repos/{repo}/labels/{label}", headers=_headers(), timeout=20)
    if r.status_code == 404:
        requests.post(f"{API}/repos/{repo}/labels", headers=_headers(), timeout=20,
                      json={"name": label, "color": "0e8a16",
                            "description": "embedded-digest 자동 발행"})


def send(subject: str, markdown: str, blocks: list[dict]) -> None:
    repo = os.environ["GITHUB_REPOSITORY"]
    label = os.environ.get("DIGEST_ISSUE_LABEL", "digest")
    _ensure_label(repo, label)

    # 이슈 본문은 65536자 제한. 넘으면 잘라내고 표시한다.
    body = markdown
    if len(body) > 65000:
        body = body[:65000] + "\n\n> (길이 제한으로 잘림)\n"

    r = requests.post(f"{API}/repos/{repo}/issues", headers=_headers(), timeout=30,
                      json={"title": subject, "body": body, "labels": [label]})
    r.raise_for_status()
    print(f"  이슈 생성: {r.json()['html_url']}")
