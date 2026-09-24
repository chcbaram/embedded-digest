"""선정 · 출력 포맷 생성 (Markdown / Slack Block Kit)."""
from __future__ import annotations

from datetime import datetime

SECTION_TITLE = {
    "news": "뉴스",
    "articles": "기술 글",
    "community": "커뮤니티",
    "releases": "릴리스",
}
SECTION_ORDER = ["releases", "news", "articles", "community"]
STAR = {3: "★★★", 2: "★★", 1: "★"}


def select(items: list[dict], limits: dict) -> list[dict]:
    """중요도 순으로 섹션별·전체 상한을 적용한다."""
    per_section = limits.get("per_section", 5)
    total = limits.get("total", 20)

    picked: list[dict] = []
    for section in SECTION_ORDER:
        cap = limits.get(section, per_section)
        rows = [i for i in items if i.get("section") == section]
        rows.sort(key=lambda r: (-r.get("importance", 1), r.get("title_ko", "")))
        picked.extend(rows[:cap])

    picked.sort(key=lambda r: (SECTION_ORDER.index(r["section"]),
                               -r.get("importance", 1)))
    return picked[:total]


def _group(items: list[dict]) -> list[tuple[str, list[dict]]]:
    return [(s, [i for i in items if i["section"] == s])
            for s in SECTION_ORDER
            if any(i["section"] == s for i in items)]


def _star(item: dict) -> str:
    """요약이 없는 모드에서는 중요도가 의미 없으므로 별을 붙이지 않는다."""
    if not (item.get("summary_ko") or item.get("reason")):
        return ""
    return STAR.get(item.get("importance", 1), "")


def markdown(items: list[dict], failures: list[tuple[str, str]],
             date: str | None = None, note: str | None = None) -> str:
    date = date or datetime.now().strftime("%Y-%m-%d")
    out = [f"# 임베디드 다이제스트 · {date}", ""]

    if not items:
        out.append("오늘은 새로 올라온 항목이 없습니다.")
    if note:
        out.append(f"> {note}\n")

    for section, rows in _group(items):
        out.append(f"## {SECTION_TITLE[section]}")
        out.append("")
        for r in rows:
            star = _star(r)
            title = r.get("title_ko") or r.get("title_orig", "")
            heading = f"### {star} [{title}]" if star else f"### [{title}]"
            out.append(f"{heading}({r['link']})")
            if r.get("title_ko") and r.get("title_orig") and r["title_ko"] != r["title_orig"]:
                out.append(f"<sub>{r['title_orig']}</sub>")
            out.append("")
            if r.get("summary_ko"):
                out.append(r["summary_ko"])
                out.append("")
            if r.get("reason"):
                out.append(f"*왜: {r['reason']}*")
                out.append("")
            out.append(f"<sub>출처: {r.get('feed', '')}</sub>")
            out.append("")

    if failures:
        out.append("---")
        out.append("<details><summary>수집 실패한 피드 " f"{len(failures)}개</summary>")
        out.append("")
        for url, reason in failures:
            out.append(f"- `{url}` — {reason}")
        out.append("")
        out.append("</details>")
    return "\n".join(out).rstrip() + "\n"


def slack_blocks(items: list[dict], failures: list[tuple[str, str]],
                 date: str | None = None, note: str | None = None) -> list[dict]:
    date = date or datetime.now().strftime("%Y-%m-%d")
    blocks: list[dict] = [{
        "type": "header",
        "text": {"type": "plain_text", "text": f"임베디드 다이제스트 · {date}"},
    }]

    if not items:
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": "오늘은 새로 올라온 항목이 없습니다."}})
    if note:
        blocks.append({"type": "context",
                       "elements": [{"type": "mrkdwn", "text": note}]})

    for section, rows in _group(items):
        blocks.append({"type": "divider"})
        blocks.append({"type": "section",
                       "text": {"type": "mrkdwn", "text": f"*{SECTION_TITLE[section]}*"}})
        for r in rows:
            star = _star(r)
            title = r.get("title_ko") or r.get("title_orig", "")
            lines = [f"{star} *<{r['link']}|{title}>*".lstrip()]
            if r.get("summary_ko"):
                lines.append(r["summary_ko"])
            blocks.append({"type": "section",
                           "text": {"type": "mrkdwn", "text": "\n".join(lines)}})
            context = []
            if r.get("reason"):
                context.append(f"왜: {r['reason']}")
            if r.get("feed"):
                context.append(r["feed"])
            if context:
                blocks.append({"type": "context", "elements": [
                    {"type": "mrkdwn", "text": " · ".join(context)}]})

    if failures:
        blocks.append({"type": "divider"})
        blocks.append({"type": "context", "elements": [
            {"type": "mrkdwn",
             "text": f"수집 실패 {len(failures)}개: "
                     + ", ".join(u.split("/")[2] for u, _ in failures[:6])}]})
    return blocks
