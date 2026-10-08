# 카카오톡 · ChatGPT MCP 서버

`mcp_server.py` — Claude Code(또는 다른 MCP 클라이언트)에서 카카오톡 '나에게 보내기'와
ChatGPT를 직접 쓰기 위한 stdio MCP 서버.

## 툴

| 툴 | 하는 일 | 비용 |
|---|---|---|
| `kakao_send_memo` | 내 카카오톡으로 메시지 전송 (최대 200자) | 무료 |
| `chatgpt_ask` | ChatGPT 범용 질의 | 토큰 과금 |
| `chatgpt_generate_content` | 업종 가드레일 적용 콘텐츠 초안 | 토큰 과금 |

`chatgpt_generate_content` 는 `generate_content.py` 의 `build_prompt()` 를 그대로 호출한다.
즉 업종별 규제 가드레일(의료법·표시광고법 등)이 파이프라인과 동일하게 적용된다.
가드레일 문구를 고칠 일이 있으면 `generate_content.py` 한 곳만 고치면 양쪽에 반영된다.

## 카카오톡으로 할 수 있는 것과 없는 것

이 서버가 쓰는 건 카카오 **메모 API('나에게 보내기')** 하나다.

- 되는 것 — 내 카카오톡으로 알림 보내기. 파이프라인 완료, 새 리드, 일일 리포트 등.
- **안 되는 것 — 고객에게 발송.** 알림톡/친구톡은 카카오 비즈니스채널 + 발송대행사
  (솔라피·알리고·NHN 등) 계약 + 템플릿 사전승인이 있어야 한다. 별도 구현이 필요하다.
- **안 되는 것 — 오픈채팅.** 카카오톡 오픈채팅은 공식 API가 아예 없다. 읽기도 쓰기도
  자동화할 수 없다. 현재 리드 유입 경로인 `open.kakao.com/o/sZ71xB5d` 는 수동 대응만 가능하다.

## 설정

### 1. 의존성

저장소 루트에 venv 를 만들어 설치한다. `.mcp.json` 이 이 경로를 가리킨다.

```bash
python3 -m venv .venv
.venv/bin/pip install -r content-agency/automation/requirements.txt
```

시스템 파이썬을 직접 쓰지 않는 이유: 배포판이 관리하는 패키지와 충돌해 설치가 막히는 경우가
있고(그러면 MCP 서버가 `ModuleNotFoundError` 로 기동 실패한다), venv 는 표준 라이브러리라
추가 도구가 필요 없다. `.venv/` 는 `.gitignore` 에 있으므로 클론한 쪽에서 한 번 실행하면 된다.

### 2. 카카오 토큰 발급

1. [카카오 개발자](https://developers.kakao.com) → 내 애플리케이션 → 앱 생성
2. **앱 키 → REST API 키** 를 복사 → `KAKAO_REST_API_KEY`
3. **카카오 로그인** 활성화 + Redirect URI 등록
4. **동의항목** 에서 `talk_message`(카카오톡 메시지 전송) 를 활성화 — 이게 없으면 전송이 403 난다
5. 카카오 로그인 인가 과정을 한 번 거쳐 `access_token` 과 `refresh_token` 획득
   → `KAKAO_ACCESS_TOKEN`, `KAKAO_REFRESH_TOKEN`

액세스 토큰은 몇 시간이면 만료된다. 서버가 401 을 받으면 리프레시 토큰으로 자동 갱신하고
한 번 재시도하므로 평소엔 신경 쓸 필요 없다. 리프레시 토큰까지 만료되면(수개월) 5번을 다시 한다.

### 3. OpenAI 키

`OPENAI_API_KEY` 를 설정한다. `OPENAI_MODEL` 로 기본 모델을 지정할 수 있고,
미설정 시 `gpt-4o-mini` 를 쓴다 — **계정에서 실제 사용 가능한 모델명으로 바꿔 두는 걸 권장한다.**
모델명이 틀리면 OpenAI 가 반환한 오류 원문이 그대로 툴 오류로 올라온다.

### 4. 환경변수 주입

`.mcp.json` 이 셸 환경변수를 그대로 읽어간다. 키는 저장소에 커밋하지 말고 셸 프로필이나
비밀 관리 도구에서 export 한다.

```bash
export KAKAO_REST_API_KEY=...
export KAKAO_ACCESS_TOKEN=...
export KAKAO_REFRESH_TOKEN=...
export OPENAI_API_KEY=...
export OPENAI_MODEL=...
```

키가 비어 있어도 서버는 정상 기동한다. 해당 툴을 호출하는 순간
"환경변수 X 가 설정되어 있지 않습니다" 오류가 뜰 뿐이다.

## 검증

```bash
python mcp_server.py --selfcheck
```

네트워크 없이 메모 템플릿 조립, 200자 제한, 업종 가드레일 프롬프트를 검사한다.
API 키 없이도 돌아간다.
