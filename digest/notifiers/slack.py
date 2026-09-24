"""Slack Incoming Webhook 전달."""
from __future__ import annotations

import os

import requests

NAME = "slack"
MAX_BLOCKS = 48  # Slack 한 메시지당 50개 제한, 여유를 둔다


def available() -> tuple[bool, str]:
    return (bool(os.environ.get("SLACK_WEBHOOK_URL")),
            "SLACK_WEBHOOK_URL 이 설정되지 않았습니다")


def send(subject: str, markdown: str, blocks: list[dict]) -> None:
    url = os.environ["SLACK_WEBHOOK_URL"]
    for i in range(0, len(blocks), MAX_BLOCKS):
        chunk = blocks[i:i + MAX_BLOCKS]
        r = requests.post(url, json={"text": subject, "blocks": chunk}, timeout=20)
        r.raise_for_status()
