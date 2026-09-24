"""RSS/Atom 수집.

피드 하나가 실패해도 나머지는 계속 진행하고, 실패 목록을 함께 돌려준다.
"""
from __future__ import annotations

import hashlib
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import feedparser
import requests

USER_AGENT = "embedded-digest/0.1 (+https://github.com/chcbaram)"
TIMEOUT = 25
RETRIES = 3
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")


@dataclass
class Entry:
    id: str
    section: str
    feed: str
    title: str
    link: str
    published: datetime | None
    summary: str

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["published"] = self.published.isoformat() if self.published else None
        return d


@dataclass
class FetchResult:
    entries: list[Entry] = field(default_factory=list)
    failures: list[tuple[str, str]] = field(default_factory=list)  # (url, 사유)


def _clean(text: str, limit: int = 600) -> str:
    text = html.unescape(TAG_RE.sub(" ", text or ""))
    text = WS_RE.sub(" ", text).strip()
    return text[:limit]


def _entry_id(section: str, entry) -> str:
    raw = entry.get("id") or entry.get("link") or entry.get("title", "")
    return hashlib.sha1(f"{section}|{raw}".encode()).hexdigest()[:16]


def _published(entry) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        t = entry.get(key)
        if t:
            return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
    return None


def _get(url: str) -> bytes:
    last = None
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT,
                             headers={"User-Agent": USER_AGENT})
            if r.status_code == 429:
                last = "HTTP 429 (rate limit)"
                time.sleep(2 ** attempt * 3)
                continue
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt)
    raise RuntimeError(last or "unknown error")


def fetch_one(section: str, url: str, cutoff: datetime | None) -> tuple[list[Entry], str | None]:
    try:
        content = _get(url)
    except Exception as e:  # noqa: BLE001 - 실패한 피드는 리포트만 하고 넘어간다
        return [], str(e)

    parsed = feedparser.parse(content)
    feed_title = _clean(parsed.feed.get("title", url), 60) or url
    out = []
    for e in parsed.entries:
        pub = _published(e)
        if cutoff and pub and pub < cutoff:
            continue
        link = e.get("link") or ""
        if not link:
            continue
        out.append(Entry(
            id=_entry_id(section, e),
            section=section,
            feed=feed_title,
            title=_clean(e.get("title", ""), 200),
            link=link,
            published=pub,
            summary=_clean(e.get("summary", "") or e.get("description", "")),
        ))
    if not parsed.entries:
        return out, "항목 0개 (피드 형식 확인 필요)"
    return out, None


def fetch_all(sections: dict[str, list[str]], max_age_hours: int | None = 36,
              workers: int = 8) -> FetchResult:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
              if max_age_hours else None)
    targets = [(sec, url) for sec, urls in sections.items() for url in (urls or [])]

    result = FetchResult()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for (sec, url), (entries, err) in zip(
                targets, ex.map(lambda t: fetch_one(t[0], t[1], cutoff), targets)):
            result.entries.extend(entries)
            if err:
                result.failures.append((url, err))

    result.entries.sort(key=lambda e: e.published or datetime.min.replace(tzinfo=timezone.utc),
                        reverse=True)
    return result
