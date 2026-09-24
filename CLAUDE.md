# embedded-digest — 임베디드 데일리 다이제스트

## 목표

임베디드 관련 뉴스, 커뮤니티 이슈, MCU·SDK·개발툴 릴리스를 매일 아침 자동으로 수집합니다.
수집한 항목은 LLM으로 중요도를 분류하고 한국어로 요약한 뒤 하나의 다이제스트로 전달합니다.
아침에 2~3분 안에 훑어볼 수 있는 분량을 목표로 합니다.

## 확정된 방향

- 방식: RSS/Atom 수집 → 중복 제거 → Claude API로 분류·요약 → 전달
- 실행 환경: GitHub Actions cron. 매일 07:00 KST에 실행합니다(UTC 기준 `0 22 * * *`).
- 상태 저장: 처리한 항목 ID를 저장소 파일(`state/seen.json`)에 커밋해 중복 전송을 막습니다. DB는 쓰지 않습니다.
- 설정: 소스 목록과 관심 키워드는 `feeds.yaml` 하나로 관리합니다. 코드를 수정하지 않고 소스를 추가하거나 뺄 수 있어야 합니다.
- 전달 채널: **Slack(Incoming Webhook) + GitHub 이슈**. `notifiers/`는 플러그인 구조이고
  `NOTIFIERS` 환경변수로 고릅니다. 메일(SMTP)도 구현되어 있으나 기본값은 아닙니다.
- 요약 모델: **`claude-sonnet-5`** (`ANTHROPIC_MODEL` 환경변수로 교체 가능).
  비용을 줄이려면 `claude-haiku-4-5`로 바꿉니다.
- 항목 수: 섹션당 5개, 전체 20개, 릴리스만 8개. `feeds.yaml`의 `limits`에서 조정합니다.
- 수집 범위: 최근 36시간(`limits.max_age_hours`). 첫 실행에서 과거 항목이 쏟아지지 않게 합니다.

## 저장소 구조

```
embedded-digest/
├── CLAUDE.md
├── README.md
├── feeds.yaml              # 소스 목록 + 관심 키워드 + 상한
├── digest/
│   ├── fetch.py            # RSS/Atom 수집 (feedparser, 실패 격리, 429 백오프)
│   ├── dedup.py            # seen.json 기반 중복 제거, 30일 지난 ID 정리
│   ├── summarize.py        # Claude API 호출, JSON 스키마 강제
│   ├── render.py           # 선정 + Markdown / Slack Block Kit 생성
│   └── notifiers/
│       ├── slack.py
│       ├── github_issue.py
│       └── email.py
├── tools/check_feeds.py    # 피드 URL 유효성 검증
├── state/seen.json
├── main.py
├── requirements.txt
└── .github/workflows/daily.yml
```

## 정보원

`feeds.yaml`에서 관리합니다. 관심 키워드는 `~/hdd/git`의 저장소 147개에서 실제로 다루는
대상(STM32 전 계열, ESP32, RP2040/2350, nRF52/54, CH32, GD32, AT32, Nuvoton, HPMicro,
QMK/ZMK/RMK/Vial, Zephyr, OpenOCD/pyOCD/probe-rs, WIZnet, CAN/FDCAN 등)을 반영했습니다.

피드를 추가·수정하면 반드시 검증합니다:

```bash
python tools/check_feeds.py
```

현재 38개 중 36개 정상. 실패 2개는 Reddit 서브레딧(`r/PrintedCircuitBoard`, `r/FPGA`)으로,
IP 단위 레이트리밋(HTTP 429)입니다. 피드 자체는 유효하며 Actions 러너에서는 통과할 수 있습니다.

## 요약 단계 요구사항

- 항목을 25개씩 배치로 묶어 호출합니다. 항목마다 호출하지 않습니다.
- `output_config.format`의 `json_schema`로 응답 형식을 강제합니다.
  항목별로 `{id, section, importance(1-3), title_ko, summary_ko(3줄 이내), reason}`.
- `interests`와 관련된 항목은 importance를 올리고, 광고성이거나 관련 없는 항목은 제외합니다.
- 릴리스 항목은 요약 대신 "주요 변경점 + breaking change 여부"를 적습니다.
- JSON 파싱에 실패하면 한 번 재시도합니다. 그래도 실패하면 요약 없이 제목과 링크만 보냅니다.
- `id`는 모델이 새로 만들지 못하게 하고, 돌려받은 뒤 원본 id와 대조해서 거릅니다.

## 운영 요구사항

- Secrets: `ANTHROPIC_API_KEY` (필수), `SLACK_WEBHOOK_URL` (Slack 사용 시).
  `GITHUB_TOKEN`은 Actions가 자동 제공하므로 등록하지 않습니다.
- 피드 하나가 실패해도 전체 실행은 계속됩니다. 실패한 피드 목록은 다이제스트 맨 아래에 표시합니다.
- 채널 하나가 실패해도 나머지는 전송합니다. 전부 실패했을 때만 `seen.json`을 갱신하지 않아
  다음 실행에서 다시 시도합니다.
- `seen.json`은 30일이 지난 ID를 정리해서 파일 크기를 제한합니다.
- 수동 실행용 `workflow_dispatch`(dry_run 옵션 포함)와 로컬 테스트용 `--dry-run`을 둡니다.

## 작업 순서

1. [x] `feeds.yaml`의 URL 유효성 검증 스크립트 작성, 죽은 피드 수정
2. [x] fetch → dedup → `--dry-run`으로 원문 목록 출력 확인
3. [ ] summarize를 붙이고 프롬프트 튜닝 (노이즈 비율 확인) — **API 키 설정 후 진행**
4. [x] notifier 구현 (slack, github_issue, email)
5. [x] GitHub Actions 워크플로 + `seen.json` 자동 커밋
6. [ ] 1주일 운영 후 소스 가감, 섹션별 항목 수 조정
