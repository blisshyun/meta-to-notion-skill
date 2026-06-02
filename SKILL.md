---
name: meta-to-notion
description: Meta(페이스북) 광고 인사이트를 자동으로 수집·분석해서 노션 페이지로 업로드합니다. 사용자가 "광고 인사이트 노션에 정리해줘" / "지난 N일 메타 광고 성과 노션에 업로드" / "광고 계정 act_xxx 인사이트 보고서 만들어줘" 같은 요청을 하거나, 광고 ID + 액세스 토큰 + 요청사항을 함께 던질 때 호출됩니다.
allowed-tools: Bash(python3:*), Read, Write
---

# meta-to-notion — 광고 인사이트 → 노션 자동화

## 동작 요약

사용자가 (1) 광고 계정 ID, (2) Meta 액세스 토큰, (3) 분석 요청사항을 주면 → 실제 Meta Graph API로 인사이트를 수집 → 분석 리포트 생성 → 노션 페이지에 업로드. 브라우저 OAuth 흐름은 사용하지 않는다.

## When to use this skill

- "광고 인사이트 노션에 올려줘"
- "지난 N일 메타 광고 성과 정리해줘"
- "act_xxx 광고 계정 분석 보고서 만들어줘"
- 사용자가 광고 계정 ID + 액세스 토큰 + 요청사항을 함께 줄 때

## Inputs (사용자에게 받기)

이미 대화나 config에 있으면 다시 묻지 말 것. 셋 중 누락된 게 있을 때만 요청.

1. **광고 계정 ID** (`act_xxx`) — config의 `ad_account_id`
2. **Meta 액세스 토큰** — config의 `meta_token`
3. **요청사항** (자유 텍스트) — 예: "지난 7일 ROAS 상위 3개 강조 / 30-40대 여성 패션 플랫폼"
4. **노션 페이지 URL** (선택) — 안 주면 config의 `default_notion_page` 사용

## Steps

### Step 0 — config 갱신 (사용자가 새 값 줬을 때만)

사용자가 메시지에서 **새로운** 광고 계정 ID나 토큰을 명시적으로 줬을 때만 실행. 이미 config에 같은 값이 있으면 건너뛴다.

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py \
  [--save-account-id <act_xxx>] \
  [--save-meta-token <TOKEN>]
```

토큰 유효성 확인이 필요할 때:
```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --validate
```

### Step 1 — 실제 광고 인사이트 수집 (+ 잘된 소재 HD URL)

> 1단계: 최근 N일 광고 인사이트 + ROAS 상위 소재 고화질 URL 수집 중…

사용자 요청에서 "지난 N일" / "최근 N일" / "Nday" 표현을 찾아 `--days N`로 매핑 (1, 7, 14, 28, 30 중 가장 가까운 값). 없으면 `--days 7`.

`--top-creatives N` 은 ROAS 상위 N개 광고에 대해 고화질 이미지 URL을 추가 수집 (기본 3개). 사용자가 "고화질 안 가져와도 됨"처럼 명시할 때만 `--top-creatives 0`.

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/fetch_insights.py \
  --days <N> --output /tmp/meta-insights.json
```

stderr 출력은 사용자에게 그대로 노출.

### Step 2 — 분석 리포트 생성

> 2단계: ROAS · CTR · CPA 계산 + 한국어 요약 5문장 생성 중…

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/analyze.py \
  --input /tmp/meta-insights.json \
  --output /tmp/meta-report.md \
  --extra "<사용자 요청사항 텍스트 — 비어있으면 '핵심 지표 요약과 ROAS 상위 3개 강조.'>"
```

### Step 3 — 노션 자동 업로드

> 3단계: 노션 페이지에 자동 업로드 중…

`--page-url` 인자는 사용자가 메시지에서 명시적으로 노션 URL을 줬을 때만 추가. 없으면 생략 → config의 `default_notion_page`가 자동 사용.

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/notion_upload.py \
  --report /tmp/meta-report.md \
  --title "Meta 광고 인사이트 보고서 — <YYYY-MM-DD>"
```

## 결과물 톤 참고 (few-shot)

Step 2의 분석 리포트를 작성하기 전에, 아래 예시들의 **구조·헤더 순서·말투·인사이트 길이**를 반드시 먼저 확인하고 같은 톤으로 작성할 것.

- `~/.claude/skills/meta-to-notion/examples/2025-05-meta-report.md`
- `~/.claude/skills/meta-to-notion/examples/2025-04-meta-report.md`

## 출력 마무리

업로드 끝나면 노션 페이지 URL을 클릭 가능한 형태로 보여주고 종료.

```
✓ 완료!

📝 노션 페이지: <URL>
```

## Errors

- **Step 1 토큰 만료/권한 부족** (HTTP 190 / 200 / 100): "Meta 토큰이 만료됐거나 권한이 부족합니다 — 새 토큰을 발급받아 `--save-meta-token <TOKEN>`으로 저장 후 다시 호출"
- **Step 1 광고 계정 ID 없음**: 사용자에게 `act_xxx` 형식 ID 요청
- **Step 3 노션 401**: "노션 페이지에 통합이 초대되지 않았습니다 — 페이지 우상단 ··· → 연결 → 통합 추가" 안내
- **Step 3 노션 페이지 URL 없음**: config의 `default_notion_page`도 비어있을 때 — 사용자에게 페이지 URL 요청

## Config 위치

`~/.config/meta-to-notion/config.json` — 토큰·계정 ID·기본 페이지 저장. chmod 600. git에 절대 올리지 말 것.

저장 가능한 필드:
- `meta_token` — Meta 액세스 토큰
- `ad_account_id` — `act_xxx` 형식
- `notion_token` — 노션 통합 토큰
- `default_notion_page` — 기본 업로드 페이지
- `meta_api_version` — 기본 v23.0
