"""state/seen.json 기반 중복 제거.

형식: {"<entry id>": "<처음 본 날짜 ISO>"}
30일이 지난 ID는 정리해서 파일이 무한정 커지지 않게 한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

RETENTION_DAYS = 30


def load(path: str | Path) -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}  # 손상된 상태 파일은 버리고 새로 시작


def filter_new(entries, seen: dict[str, str]):
    out, batch_ids = [], set()
    for e in entries:
        if e.id in seen or e.id in batch_ids:
            continue
        batch_ids.add(e.id)
        out.append(e)
    return out


def prune(seen: dict[str, str], retention_days: int = RETENTION_DAYS) -> dict[str, str]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    kept = {}
    for k, v in seen.items():
        try:
            if datetime.fromisoformat(v) >= cutoff:
                kept[k] = v
        except (TypeError, ValueError):
            continue  # 날짜를 못 읽으면 만료 처리
    return kept


def save(path: str | Path, seen: dict[str, str], new_entries) -> dict[str, str]:
    now = datetime.now(timezone.utc).isoformat()
    merged = prune(seen)
    for e in new_entries:
        merged.setdefault(e.id, now)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(merged, ensure_ascii=False, indent=0, sort_keys=True),
                 encoding="utf-8")
    return merged
