# meta-to-notion — 광고 인사이트 → 노션 자동화 스킬

Claude Code에서 자연어로 호출하면 Meta 광고 인사이트를 수집·분석해서 노션 페이지에 자동 업로드하는 스킬입니다.

```
사용자:  "지난 7일 광고 인사이트 노션에 정리해줘"
   ↓
Claude:  [fetch] → [analyze] → [upload]
   ↓
   📝 새 노션 페이지 URL
```

---

## 디렉토리 구조

```
meta-to-notion/
├── SKILL.md                   ← 자동 매칭용 스킬 정의 (Claude가 읽음)
├── README.md                  ← 지금 보는 파일
└── scripts/
    ├── auth.py                ← config 저장·검증
    ├── fetch_insights.py      ← Meta Graph API 호출 → JSON 저장
    ├── analyze.py             ← JSON → 마크다운 리포트 (ROAS·CTR·CPA)
    └── notion_upload.py       ← 마크다운 → 노션 페이지 업로드
```

추가로 슬래시 커맨드 `/meta-to-notion`은 `~/.claude/commands/meta-to-notion.md`에 별도 정의되어 있습니다.

## 데이터 흐름

```
config.json (~/.config/meta-to-notion/)
   ├── meta_token            ┐
   ├── ad_account_id         │
   ├── notion_token          ├─→ 4개 스크립트가 공통 참조
   ├── default_notion_page   │
   └── meta_api_version      ┘

[fetch_insights.py]
   Meta Graph API
     /{account}/ads          ← 광고 메타·크리에이티브 (+ object_story_spec)
     /{account}/insights     ← 노출/클릭/지출/구매
     /{video_id}?fields=thumbnails  ← ROAS 상위 N개의 비디오 썸네일 (HD)
     /{video_id}?fields=source      ← ROAS 상위 N개의 mp4 source URL
   → /tmp/meta-insights.json
     (ROAS 상위 N개에 creative.hd_image_url + 비디오면 creative.hd_video_url 추가)

[analyze.py]
   ROAS = purchase_value / spend
   CPA  = spend / purchases
   + 한국어 요약 5문장
   + 잘된 소재 HD 미리보기 섹션
       이미지 광고:   ![alt](image_url)
       비디오 광고:   !video[alt](video_url) + ![alt](thumb_url)  (썸네일 폴백)
   → /tmp/meta-report.md

[notion_upload.py]
   markdown → notion blocks (heading/bullet/table/image/video)
   POST /v1/pages   (자식 페이지 생성)
   PATCH /v1/blocks/{id}/children   (100개 초과분)
   → 새 노션 페이지 URL
     (이미지·영상이 inline으로 노출 — 영상은 노션에서 바로 재생)
```

---

## 설치 (5분)

### 1. 스킬 폴더 복사

```bash
# 이 폴더를 그대로 ~/.claude/skills/ 아래로 복사
cp -r meta-to-notion ~/.claude/skills/

# (선택) 슬래시 커맨드도 쓰려면
cp meta-to-notion.md ~/.claude/commands/   # 별도 받았다면
```

### 2. 토큰 4종 준비

| 항목 | 받는 곳 | 형식 |
|---|---|---|
| Meta 액세스 토큰 | https://developers.facebook.com/tools/explorer (권한: `ads_read`) | `EAA...` |
| 광고 계정 ID | Meta 광고 관리자, 또는 Explorer에서 `me/adaccounts` 조회 | `act_숫자` |
| 노션 통합 토큰 | https://www.notion.so/my-integrations → New integration | `ntn_...` 또는 `secret_...` |
| 업로드 받을 노션 페이지 URL | 노션 페이지 우상단 ··· → Connections → 본인 통합 추가 | `https://www.notion.so/...` |

> ⚠️ 노션 페이지에 통합을 **반드시 초대**해야 합니다 (안 하면 401). 가장 흔한 실수.

### 3. config 저장

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py \
  --save-meta-token "EAA..." \
  --save-account-id "act_xxxxxxxxxx" \
  --save-notion-token "ntn_..." \
  --save-notion-page "https://www.notion.so/..."
```

저장 위치: `~/.config/meta-to-notion/config.json` (chmod 600 자동 적용)

### 4. 토큰 검증

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --validate
```

`✓ Meta 토큰 검증: OK — id=... name=...` 가 나오면 준비 끝.

---

## 사용

### Claude Code 대화에서 자연어로

```
지난 7일 광고 인사이트 노션에 올려줘
최근 30일 메타 광고 성과 정리, ROAS 상위 3개 강조해서
```

### 슬래시 커맨드

```
/meta-to-notion 지난 7일 ROAS 상위 강조
```

### 수동 실행 (디버깅용)

```bash
# --top-creatives N: ROAS 상위 N개 광고의 고화질 이미지 URL 추가 수집 (기본 3, 0=비활성)
python3 scripts/fetch_insights.py --days 7 --top-creatives 3 --output /tmp/insights.json
python3 scripts/analyze.py --input /tmp/insights.json --output /tmp/report.md \
                           --extra "ROAS 상위 3개 강조"
python3 scripts/notion_upload.py --report /tmp/report.md \
                                 --title "Meta 광고 보고서 — 2026-05-09"
```

### 잘된 소재 고화질 + 영상 재생

`fetch_insights.py`는 ROAS 상위 N개(기본 3) 광고에 대해 두 종류의 미디어 URL을 추가 수집합니다:

**(1) HD 이미지 URL** — `creative.hd_image_url` (참고: `Meta_API_Toolkit/figma-plugin`의 `images.js` 패턴)
1. 비디오 광고면 `/{video_id}?fields=thumbnails{...}` 에서 가장 큰 썸네일
2. `creative.object_story_spec.link_data.picture` (링크 광고)
3. `creative.object_story_spec.photo_data.url` (사진 광고)
4. `creative.object_story_spec.video_data.image_url` (비디오 광고 커버)
5. `creative.image_url`
6. `creative.thumbnail_url`

**(2) 비디오 source URL** — `creative.hd_video_url`
- 비디오 광고에 한해 `/{video_id}?fields=source` 호출로 실제 mp4 URL 획득
- Meta가 발급하는 signed URL이므로 만료 시간 있음 — 노션에 빠르게 업로드한 직후엔 정상 재생
- 만료 후엔 노션의 비디오 블록이 깨질 수 있으므로 같은 페이지의 썸네일 image block을 폴백으로 함께 출력

`analyze.py`가 보고서에 마크다운으로 삽입:
- 이미지 광고: `![제목](url)` → 노션 image block
- 비디오 광고: `!video[제목](video_url)` + `![제목](thumb_url)` → 노션 video block (재생 가능) + image block (썸네일)

---

## 학생용 — 이 스킬을 참고해서 본인 스킬 만들기

이 스킬을 답안지처럼 활용하세요.

### 추천 학습 순서

1. **`SKILL.md` 정독** — frontmatter(name/description/allowed-tools)와 본문 절차가 어떻게 연결되는지 확인. 특히 `description`이 자연어 매칭의 키.

2. **각 스크립트 읽기** (위쪽 docstring 위주):
   - `auth.py` — config가 어떻게 저장되고 검증되는지
   - `fetch_insights.py` — Graph API URL 구성, 페이지네이션, 필드 선택
   - `analyze.py` — JSON에서 어떤 지표를 어떻게 뽑는지
   - `notion_upload.py` — 마크다운을 노션 블록으로 변환하는 패턴

3. **본인 스킬로 변형해보기** — 추천 실습 아이디어:
   - GA4 데이터로 바꿔보기 (소스만 다른 동일 구조)
   - 슬랙 업로드로 바꿔보기 (`notion_upload.py` 자리에 `slack_upload.py`)
   - 카카오 모먼트, Google Ads 등 다른 광고 플랫폼으로 확장

4. **자기 스킬 폴더 만들기**:
   ```bash
   cp -r ~/.claude/skills/meta-to-notion ~/.claude/skills/<자기이름>-광고분석
   ```
   그리고 `SKILL.md`의 `name`/`description`, 각 스크립트 내 `CONFIG_PATH`를 새 이름으로 수정.

### 자주 막히는 부분

- **노션 401**: 페이지에 통합 초대 안 함. 노션 페이지 우상단 ··· → Connections.
- **Meta 토큰 만료**: Graph API Explorer 토큰은 1~2시간. 다시 발급 → `auth.py --save-meta-token`.
- **광고 0개 결과**: 토큰 권한 부족 또는 해당 계정에 최근 활성 광고가 없음. `me/adaccounts`로 본인이 접근 가능한 계정 목록 확인.
- **노션 표가 안 그려짐**: 마크다운 표 분리자(`|---|`) 행이 빠졌는지 확인.

---

## 의존성

- Python 3.9+ (표준 라이브러리만 사용 — `urllib`, `json`, `re`, `argparse`)
- 외부 패키지 없음

## 보안 주의

- `~/.config/meta-to-notion/config.json`은 chmod 600으로 자동 설정
- 절대 git에 커밋하지 말 것 (`.gitignore`에 `config.json` 추가 권장)
- Meta App Secret을 채팅·로그·이슈 트래커에 붙여넣지 말 것
