#!/usr/bin/env python3
"""feeds.yaml에 적힌 모든 피드 URL이 실제로 살아있고 파싱되는지 확인한다.

사용법:
    python tools/check_feeds.py [feeds.yaml] [--json]

각 URL마다 HTTP 상태, 최종 URL(리다이렉트), 파싱된 항목 수, 최신 항목 제목을 출력한다.
하나라도 실패하면 종료 코드 1.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor

import feedparser
import requests
import yaml

UA = "embedded-digest/0.1 (+https://github.com/; feed checker)"
TIMEOUT = 20


def check(url: str) -> dict:
    result = {"url": url, "ok": False, "status": None, "final_url": None,
              "entries": 0, "latest": None, "error": None}
    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": UA},
                         allow_redirects=True)
        result["status"] = r.status_code
        result["final_url"] = r.url if r.url != url else None
        if r.status_code != 200:
            result["error"] = f"HTTP {r.status_code}"
            return result
        parsed = feedparser.parse(r.content)
        result["entries"] = len(parsed.entries)
        if parsed.entries:
            result["latest"] = parsed.entries[0].get("title", "")[:80]
            result["ok"] = True
        else:
            bozo = getattr(parsed, "bozo_exception", None)
            result["error"] = f"항목 0개 ({bozo})" if bozo else "항목 0개"
    except Exception as e:  # noqa: BLE001 - 어떤 실패든 리포트만 하고 계속 진행
        result["error"] = f"{type(e).__name__}: {e}"
    return result


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    path = args[0] if args else "feeds.yaml"
    as_json = "--json" in sys.argv

    cfg = yaml.safe_load(open(path, encoding="utf-8"))
    targets = [(sec, url) for sec, urls in cfg["sections"].items() for url in urls]

    with ThreadPoolExecutor(max_workers=8) as ex:
        results = list(ex.map(lambda t: {**check(t[1]), "section": t[0]}, targets))

    if as_json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            mark = "OK  " if r["ok"] else "FAIL"
            print(f"{mark} [{r['section']}] {r['url']}")
            print(f"       status={r['status']} entries={r['entries']}")
            if r["final_url"]:
                print(f"       -> redirect: {r['final_url']}")
            if r["latest"]:
                print(f"       latest: {r['latest']}")
            if r["error"]:
                print(f"       error: {r['error']}")

    bad = [r for r in results if not r["ok"]]
    print(f"\n합계: {len(results)}개 중 {len(results) - len(bad)}개 정상, {len(bad)}개 실패")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
