# embedded-digest

임베디드 관련 뉴스 · 커뮤니티 · SDK 릴리스를 매일 아침 모아서 한국어로 요약해 보내줍니다.
RSS/Atom 수집 → 중복 제거 → Claude API 분류·요약 → Slack / GitHub 이슈 전달.

매일 07:00 KST(= UTC 22:00)에 GitHub Actions cron으로 돕니다.

## 빠른 시작

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

# 1. 피드가 살아있는지 확인
.venv/bin/python tools/check_feeds.py

# 2. LLM 없이 수집만 확인
.venv/bin/python main.py --dry-run --no-summary

# 3. 요약까지 확인 (전송은 안 함)
export ANTHROPIC_API_KEY=sk-ant-...
.venv/bin/python main.py --dry-run
```

`--dry-run`은 `state/seen.json`을 건드리지 않으므로 몇 번이든 반복해도 됩니다.

## 설정 — `feeds.yaml`

코드를 고치지 않고 이 파일만 수정하면 됩니다.

| 키 | 설명 |
|---|---|
| `limits.per_section` | 섹션당 최대 항목 수 (기본 5) |
| `limits.total` | 하루 전체 최대 항목 수 (기본 20) |
| `limits.releases` | 릴리스 섹션만 별도 상한 (기본 8) |
| `limits.max_age_hours` | 이보다 오래된 항목은 버림 (기본 36) |
| `interests` | 요약할 때 중요도를 올릴 키워드 |
| `sections` | `news` / `articles` / `community` / `releases` 별 피드 URL |

## 요약 모드

현재 기본값은 **요약 없이(`--no-summary`) 발행**입니다. LLM을 호출하지 않으므로 비용이 없고,
수집·중복 제거·섹션 분류·상한 적용은 그대로 동작해 제목과 링크만 정리해서 보냅니다.

LLM 요약을 켜려면 `ANTHROPIC_API_KEY` Secret을 등록하고:

```bash
gh variable set SUMMARIZE --body true
```

수동 실행 시에는 Run workflow 화면의 `summarize` 체크박스로 한 번만 켤 수도 있습니다.

## 전달 채널

`NOTIFIERS` 환경변수로 고릅니다(쉼표 구분). 기본값 `github_issue`.
한 채널이 실패해도 나머지는 전송하고, 전부 실패했을 때만 `seen.json`을 갱신하지 않습니다.

| 채널 | 필요한 환경변수 |
|---|---|
| `slack` | `SLACK_WEBHOOK_URL` |
| `github_issue` | `GITHUB_TOKEN`, `GITHUB_REPOSITORY` (Actions에서는 자동) |
| `email` | `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_TO`, (선택) `SMTP_PORT`, `MAIL_FROM` |

`github_issue`는 매일 이슈 하나를 `digest` 라벨로 만듭니다. 라벨은 `DIGEST_ISSUE_LABEL`로 바꿉니다.

## GitHub Actions 설정

**Secrets** (Settings → Secrets and variables → Actions)

- `ANTHROPIC_API_KEY` — LLM 요약(`SUMMARIZE=true`)을 쓸 때만 필요
- `SLACK_WEBHOOK_URL` — Slack을 쓸 때만. 없으면 로그에 경고만 남기고 건너뜁니다.
- `GITHUB_TOKEN`은 Actions가 자동으로 제공하므로 등록하지 않습니다.

**Variables** (선택)

- `ANTHROPIC_MODEL` — 기본 `claude-sonnet-5`. 비용을 줄이려면 `claude-haiku-4-5`.
- `NOTIFIERS` — 기본 `github_issue`. Slack을 추가하려면 `slack,github_issue`.
- `SUMMARIZE` — 기본 `false`. `true`로 두면 LLM 요약을 사용합니다.

수동 실행은 Actions 탭 → `daily-digest` → Run workflow. `dry_run` 체크 시 전송 없이 로그만 남습니다.

## 동작 방식

```
feeds.yaml ─▶ fetch  ─▶ dedup ─▶ summarize ─▶ render ─▶ notifiers
              (병렬)    (seen.json)  (Claude)   (md/blocks)  (slack/issue/mail)
```

- 피드 하나가 실패해도 전체 실행은 계속되고, 실패 목록은 다이제스트 맨 아래에 붙습니다.
- HTTP 429는 지수 백오프로 3회까지 재시도합니다. Reddit이 자주 걸립니다.
- 요약은 25개씩 배치로 한 번에 호출하고, `output_config`의 JSON 스키마로 형식을 강제합니다.
  파싱에 실패하면 한 번 재시도하고, 그래도 실패하면 제목과 링크만 보냅니다.
- `state/seen.json`은 30일이 지난 ID를 정리합니다.

## 파일

```
feeds.yaml                  소스 + 관심 키워드 + 상한
main.py                     파이프라인
digest/fetch.py             수집 (실패 격리, 재시도)
digest/dedup.py             seen.json 중복 제거 / 정리
digest/summarize.py         Claude 호출, JSON 스키마 강제
digest/render.py            선정 + Markdown / Slack Block Kit
digest/notifiers/           slack.py, github_issue.py, email.py
tools/check_feeds.py        피드 URL 유효성 검증
state/seen.json             처리한 항목 ID
```
