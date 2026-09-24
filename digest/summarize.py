"""Claude API로 항목을 분류 · 한국어 요약한다.

- 항목은 배치로 묶어 호출한다(항목마다 호출하지 않음).
- output_config.format(json_schema)으로 JSON 형식을 강제한다.
- 실패하면 한 번 재시도하고, 그래도 안 되면 요약 없이 제목+링크만 넘긴다.
"""
from __future__ import annotations

import json
import logging
import os

import anthropic

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-sonnet-5"
BATCH_SIZE = 25
MAX_TOKENS = 16000

SECTIONS = ["news", "articles", "community", "releases"]

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "section": {"type": "string", "enum": SECTIONS},
                    "importance": {"type": "integer", "enum": [1, 2, 3]},
                    "title_ko": {"type": "string"},
                    "summary_ko": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "section", "importance", "title_ko",
                             "summary_ko", "reason"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SYSTEM = """\
너는 임베디드 개발자 한 명을 위한 데일리 다이제스트 편집자다.
입력으로 RSS 항목 목록을 받아, 읽을 가치가 있는 것만 골라 한국어로 요약한다.

판단 기준
- 아래 "관심 키워드"에 해당하는 항목은 importance를 올린다.
- 광고, 제품 홍보, 쿠폰, 채용, 단순 재게시, 내용 없는 질문글은 결과에서 아예 뺀다.
- 판단이 애매하면 빼는 쪽을 택한다. 분량이 적은 편이 낫다.

importance
- 3: 직접 쓰는 칩/툴에 영향이 있다. 새 실리콘, breaking change, 중요한 버그/보안 이슈.
- 2: 읽어둘 만하다. 관련 분야의 의미 있는 기술 글이나 소식.
- 1: 참고용. 관심은 가지만 지금 당장은 아니다.

작성 규칙
- title_ko: 한국어 제목. 칩 이름·툴 이름·버전 같은 고유명사는 원문 그대로 둔다.
- summary_ko: 3줄 이내. 사실만 쓴다. "~에 대해 다룹니다" 같은 빈 문장은 쓰지 않는다.
- reason: 왜 이 사람에게 중요한지 한 줄. 관심 키워드와 연결해서 쓴다.
- section 은 입력에 주어진 값을 그대로 유지한다.

releases 섹션은 요약 대신 이렇게 쓴다
- summary_ko 에 "주요 변경점"과 "breaking change 여부"를 적는다.
- breaking change가 있으면 첫 줄에 "breaking:" 으로 시작해 명시한다.
- 확인이 안 되면 추측하지 말고 "릴리스 노트 확인 필요"라고 적는다.

id 는 입력에 주어진 값을 그대로 돌려준다. 절대 새로 만들지 않는다.
제외한 항목은 items 에 넣지 않는다.
"""


def _payload(entries, interests: list[str]) -> str:
    items = [{
        "id": e.id,
        "section": e.section,
        "feed": e.feed,
        "title": e.title,
        "summary": e.summary[:500],
    } for e in entries]
    return (
        "관심 키워드:\n" + "\n".join(f"- {k}" for k in interests)
        + "\n\n항목:\n" + json.dumps(items, ensure_ascii=False, indent=1)
    )


def _call(client, model: str, entries, interests) -> list[dict]:
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM,
        thinking={"type": "adaptive"},
        output_config={
            "effort": "medium",
            "format": {"type": "json_schema", "schema": SCHEMA},
        },
        messages=[{"role": "user", "content": _payload(entries, interests)}],
    )
    text = next(b.text for b in response.content if b.type == "text")
    return json.loads(text)["items"]


def summarize(entries, interests: list[str], model: str | None = None) -> tuple[list[dict], bool]:
    """(요약 결과, 성공 여부)를 돌려준다.

    실패 시 빈 리스트 + False 를 돌려주고, 호출한 쪽에서 제목/링크만 발송한다.
    """
    if not entries:
        return [], True

    model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL)
    client = anthropic.Anthropic()

    results: list[dict] = []
    for i in range(0, len(entries), BATCH_SIZE):
        batch = entries[i:i + BATCH_SIZE]
        for attempt in (1, 2):
            try:
                results.extend(_call(client, model, batch, interests))
                break
            except (json.JSONDecodeError, KeyError, StopIteration) as e:
                log.warning("배치 %d 파싱 실패 (%d회차): %s", i // BATCH_SIZE, attempt, e)
                if attempt == 2:
                    return [], False
            except anthropic.APIError as e:
                log.warning("배치 %d API 오류 (%d회차): %s", i // BATCH_SIZE, attempt, e)
                if attempt == 2:
                    return [], False

    by_id = {e.id: e for e in entries}
    return [r for r in results if r.get("id") in by_id], True


def attach(entries, summaries: list[dict]) -> list[dict]:
    """요약 결과에 원본 링크·피드명을 붙인다."""
    by_id = {e.id: e for e in entries}
    out = []
    for s in summaries:
        e = by_id[s["id"]]
        out.append({**s, "link": e.link, "feed": e.feed,
                    "title_orig": e.title,
                    "published": e.published.isoformat() if e.published else None})
    return out
