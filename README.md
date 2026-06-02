# meta-to-notion 스킬

Claude Code에서 **"지난 7일 광고 인사이트 노션에 정리해줘"** 한 줄만 쳐도, Meta(페이스북) 광고 성과를 자동으로 수집·분석해서 노션 페이지에 보고서로 올려주는 스킬이에요.

```
사용자: "지난 7일 광고 인사이트 노션에 정리해줘"
   ↓
Claude: 광고 데이터 수집 → 분석 → 노션 업로드
   ↓
📝 새 노션 페이지 URL 출력
```

---

## 누가 쓰는 거예요?

- Meta(페이스북·인스타) 광고를 돌리는 마케터
- 매주·매월 광고 성과 보고서를 노션에 정리해야 하는 사람
- Claude Code(데스크탑 앱)를 이미 쓰고 있는 사람

---

## 설치하기 (5분)

### 0. 미리 준비할 것

- **Claude Code 데스크탑 앱** 설치돼 있어야 함 → [claude.com/code](https://claude.com/code)
- **Meta 광고 액세스 토큰** (마케팅 API 권한 포함)
- **노션 통합 토큰** + 보고서가 올라갈 **노션 페이지 URL**

> 토큰 발급법을 모르겠다면 ChatGPT나 Claude에게 "Meta 마케팅 API 액세스 토큰 발급법 알려줘" / "Notion Integration 토큰 발급법 알려줘" 라고 물어보세요.

### 1. 이 레포 다운로드

터미널을 열고 (맥은 `Cmd+Space` → "터미널" 검색), 아래 명령어를 그대로 복사해서 붙여넣고 엔터:

```bash
git clone https://github.com/blisshyun/meta-to-notion-skill ~/.claude/skills/meta-to-notion
```

> 💡 **이게 무슨 뜻이냐면**: 깃헙에 올려둔 스킬 폴더를 통째로 다운로드해서, Claude가 인식하는 위치(`~/.claude/skills/`)에 `meta-to-notion`이라는 이름으로 저장한다는 뜻이에요. 압축 풀기 + 옮기기를 한 번에 해주는 거예요.

### 2. 토큰 저장하기

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --save-meta-token "EAA로_시작하는_본인의_Meta_토큰"
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --save-account-id "act_본인의_광고계정_ID"
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --save-notion-token "ntn_으로_시작하는_본인의_노션_토큰"
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --save-notion-page "https://www.notion.so/본인의_노션_페이지_URL"
```

토큰 잘 저장됐는지 확인:

```bash
python3 ~/.claude/skills/meta-to-notion/scripts/auth.py --validate
```

✓ 표시가 뜨면 성공이에요.

### 3. 노션 페이지에 통합(Integration) 초대하기

토큰만 저장해도 노션은 **"누가 이 페이지를 수정할 수 있다"** 를 따로 허락해줘야 작동해요.

1. 보고서를 올릴 노션 페이지 열기
2. 우측 상단 `···` 클릭 → **연결** → **연결 추가**
3. 본인이 만든 통합(Integration) 이름 검색해서 초대

### 4. Claude Code 켜고 테스트

Claude Code 데스크탑 앱을 열고 (이미 켜져 있었다면 한 번 껐다 켜기) 아래처럼 물어보세요:

```
지난 7일 메타 광고 인사이트 노션에 정리해줘
```

Claude가 알아서 이 스킬을 호출해서 노션 페이지 URL을 돌려주면 완료!

---

## 자주 묻는 질문

**Q. 토큰을 깃헙에 같이 올린 거 아니에요?**
아니요. 토큰은 본인 컴퓨터의 `~/.config/meta-to-notion/config.json`에만 저장돼요. 이 파일은 `.gitignore`로 막아놔서 깃헙에 절대 안 올라갑니다.

**Q. 토큰이 만료됐어요.**
Meta 토큰은 보통 60일이면 만료돼요. 새 토큰 받아서 위 2단계의 `--save-meta-token` 명령만 다시 실행하면 갱신됩니다.

**Q. "지난 30일"로 바꿔서 부르고 싶어요.**
그냥 "지난 30일 광고 인사이트 노션에 정리해줘" 라고 자연어로 말하면 됩니다. Claude가 알아서 N일을 인식해요.

**Q. 결과물이 묘하게 다르게 나오는데요?**
Claude 모델 버전을 **Opus 4.7** 로 맞춰주세요. Sonnet/Haiku는 같은 스킬이라도 출력 스타일이 살짝 달라질 수 있어요.

---

## 더 자세한 기술 문서

스킬 내부 동작 방식(스크립트별 역할, 데이터 흐름, 노션 블록 변환 규칙 등)이 궁금하면 [INTERNALS.md](./INTERNALS.md)를 봐주세요.

---

## 라이선스 / 면책

개인 작업용으로 만든 스킬이라 자유롭게 가져다 쓰셔도 됩니다. 단, 본인 광고 토큰·노션 토큰은 본인이 잘 관리해주세요 — 유출 시 책임지지 않습니다.
