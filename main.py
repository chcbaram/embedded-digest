#!/usr/bin/env python3
"""embedded-digest — 임베디드 데일리 다이제스트.

사용 예:
    python main.py --dry-run              # 수집 + 요약만, 전송 없이 stdout 출력
    python main.py --dry-run --no-summary # LLM 호출 없이 수집 결과만 확인
    python main.py                        # 정상 실행 (NOTIFIERS 채널로 전송)
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime

import yaml

from digest import dedup, fetch, notifiers, render, summarize

log = logging.getLogger("digest")


def parse_args(argv=None):
    p = argparse.ArgumentParser(description="임베디드 데일리 다이제스트")
    p.add_argument("--config", default="feeds.yaml")
    p.add_argument("--state", default="state/seen.json")
    p.add_argument("--dry-run", action="store_true",
                   help="전송하지 않고 stdout에 출력하며, seen.json도 쓰지 않는다")
    p.add_argument("--no-summary", action="store_true",
                   help="LLM 호출을 건너뛴다 (수집/중복제거 확인용)")
    p.add_argument("--notifiers", default=None,
                   help="쉼표 구분. 기본값은 NOTIFIERS 환경변수 또는 slack")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(levelname)s %(message)s")

    cfg = yaml.safe_load(open(args.config, encoding="utf-8"))
    limits = cfg.get("limits", {}) or {}
    interests = cfg.get("interests", []) or []

    # 1. 수집
    result = fetch.fetch_all(cfg["sections"], limits.get("max_age_hours", 36))
    log.info("수집: %d개 항목, 실패 피드 %d개", len(result.entries), len(result.failures))
    for url, reason in result.failures:
        log.warning("  실패 %s — %s", url, reason)

    # 2. 중복 제거
    seen = dedup.load(args.state)
    new_entries = dedup.filter_new(result.entries, seen)
    log.info("중복 제거 후: %d개 (기존 seen %d개)", len(new_entries), len(seen))

    # 3. 요약
    summarized = True
    if args.no_summary:
        items = [{"id": e.id, "section": e.section, "importance": 1,
                  "title_ko": "", "summary_ko": "", "reason": ""}
                 for e in new_entries]
        summarized = False
    else:
        raw, summarized = summarize.summarize(new_entries, interests)
        if summarized:
            items = raw
            log.info("요약: %d개 항목 유지 (%d개 제외)",
                     len(items), len(new_entries) - len(items))
        else:
            log.warning("요약 실패 — 제목과 링크만 전송합니다")
            items = [{"id": e.id, "section": e.section, "importance": 1,
                      "title_ko": "", "summary_ko": "", "reason": ""}
                     for e in new_entries]

    items = summarize.attach(new_entries, items)
    picked = render.select(items, limits)
    log.info("선정: %d개", len(picked))

    date = datetime.now().strftime("%Y-%m-%d")
    subject = f"임베디드 다이제스트 · {date} ({len(picked)}건)"
    md = render.markdown(picked, result.failures, date, summarized)
    blocks = render.slack_blocks(picked, result.failures, date, summarized)

    # 4. 전달
    if args.dry_run:
        print("\n" + "=" * 60)
        print(md)
        print("=" * 60)
        log.info("dry-run: 전송하지 않았고 seen.json도 갱신하지 않았습니다")
        return 0

    failed_channels = []
    for mod in notifiers.load(args.notifiers):
        ok, why = mod.available()
        if not ok:
            log.error("%s 건너뜀 — %s", mod.NAME, why)
            failed_channels.append(mod.NAME)
            continue
        try:
            mod.send(subject, md, blocks)
            log.info("%s 전송 완료", mod.NAME)
        except Exception as e:  # noqa: BLE001 - 한 채널이 죽어도 나머지는 보낸다
            log.error("%s 전송 실패: %s", mod.NAME, e)
            failed_channels.append(mod.NAME)

    if failed_channels and len(failed_channels) == len(notifiers.load(args.notifiers)):
        log.error("모든 채널 전송 실패 — seen.json을 갱신하지 않습니다")
        return 1

    dedup.save(args.state, seen, new_entries)
    log.info("seen.json 갱신 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
