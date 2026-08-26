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
