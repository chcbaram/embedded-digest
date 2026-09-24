"""전달 채널 플러그인.

각 모듈은 send(subject, markdown, blocks) 함수와 available() 을 제공한다.
NOTIFIERS 환경변수(쉼표 구분)로 사용할 채널을 고른다. 기본값: slack
"""
from __future__ import annotations

import importlib
import os

KNOWN = ["slack", "github_issue", "email"]


def load(names: str | None = None):
    names = names or os.environ.get("NOTIFIERS", "slack")
    out = []
    for name in [n.strip() for n in names.split(",") if n.strip()]:
        if name not in KNOWN:
            raise ValueError(f"알 수 없는 notifier: {name} (가능: {', '.join(KNOWN)})")
        out.append(importlib.import_module(f"digest.notifiers.{name}"))
    return out
