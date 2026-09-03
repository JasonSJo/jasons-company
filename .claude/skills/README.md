# Skills

## ponytail (v4.9.0, MIT)

출처: https://github.com/DietrichGebert/ponytail (commit `2ed6c52`)

`/plugin`(마켓플레이스 설치)이 이 환경에서 동작하지 않아, 플러그인을 수동으로
같은 구성으로 풀어 넣었다 — 스킬 6종 + Node 훅 3개.

### 스킬 (`.claude/skills/`)

- `ponytail` — 게으른 시니어 개발자 모드 (lite / full / ultra)
- `ponytail-review` — 변경분 오버엔지니어링 리뷰
- `ponytail-audit` — 레포 전체 오버엔지니어링 감사
- `ponytail-debt` — `ponytail:` 주석 수집 → 부채 원장
- `ponytail-gain` — 벤치마크 스코어보드
- `ponytail-help` — 명령어 레퍼런스

### 훅 (`.claude/hooks/`, `.claude/settings.json`)

- `ponytail-activate.js` — SessionStart: 룰셋 주입 + 모드 플래그
- `ponytail-mode-tracker.js` — UserPromptSubmit: `/ponytail lite|full|ultra|off` 추적
- `ponytail-subagent.js` — SubagentStart: 서브에이전트에 모드 전파

원본은 `${CLAUDE_PLUGIN_ROOT}` 를 쓰지만 여기선 `${CLAUDE_PROJECT_DIR}/.claude/hooks/`
로 바꿨다. `ponytail-instructions.js` 가 `../skills/ponytail/SKILL.md` 를 읽으므로
`hooks/` 와 `skills/` 는 반드시 `.claude/` 아래 나란히 있어야 한다.

`node` 가 PATH 에 있어야 한다. 없으면 스킬은 그대로 동작하고 always-on 활성화만 빠진다.

끄기: 프롬프트에 `/ponytail off` 또는 "stop ponytail". 완전 제거는
`.claude/settings.json` 의 hooks 블록 삭제.

업데이트: 위 레포에서 `skills/` 와 `hooks/` 를 다시 복사하면 된다.

---

## 업무 스킬 팩 4종 (84개)

`/plugin` 이 이 환경에 없어 마켓플레이스 레포를 클론해 `skills/` 만 복사했다.
`evals/`(팩 제작자의 테스트 픽스처)는 제외. 실행되는 스크립트는 포함돼 있지 않다.

| 팩 | 개수 | 출처 | commit | 라이선스 |
|---|---|---|---|---|
| finance | 8 | anthropics/knowledge-work-plugins | `f30dc63` | LICENSE.knowledge-work-plugins |
| legal | 9 | anthropics/knowledge-work-plugins | `f30dc63` | 〃 |
| marketing | 49 | coreyhaines31/marketingskills | `d4ff28a` | LICENSE.marketingskills |
| social-media | 17 | charlie947/social-media-skills | `d2e9487` | LICENSE.social-media-skills |

finance·legal 은 Anthropic 공식, marketing·social 은 커뮤니티 제작이다.

### 플러그인 설치와 다른 점

플러그인이 아니라 **프로젝트 스킬**로 넣었기 때문에 이름 앞에 팩 이름이 붙지 않는다.
가이드에 나오는 `/finance:variance-analysis` 가 아니라 그냥 `variance-analysis` 로 부른다.

### 먼저 할 일

1. **`voice-builder` 를 가장 먼저 실행한다.** social 팩의 나머지 16개가 그 결과 파일
   (`about-me.md`, `voice.md`)을 읽고 나서야 글을 쓴다. 건너뛰면 전부 남의 말투로 나온다.
2. `copywriting` 하나만 이 사업(업종 전문 콘텐츠 대행)의 말투·상품·가격에 맞게 고친다.
   한 번에 다 고치려 하지 말 것.

수정은 이 디렉터리의 복사본에서 바로 하면 된다 — 플러그인이 아니라 덮어쓰기 위험이 없다.

### 빼는 법

스킬 90개가 매 세션 로드되어 컨텍스트를 차지한다. 안 쓰는 팩은 디렉터리째 지우면 된다.
