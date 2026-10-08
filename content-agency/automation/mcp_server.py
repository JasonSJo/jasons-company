#!/usr/bin/env python3
"""
카카오톡 + ChatGPT MCP 서버 (stdio)

툴 3개:
  kakao_send_memo          — 카카오톡 '나에게 보내기'. 파이프라인 결과·리드 알림을 내 카톡으로.
  chatgpt_ask              — ChatGPT 범용 질의.
  chatgpt_generate_content — 업종 콘텐츠 초안. generate_content.build_prompt 를 그대로 재사용한다.

⚠️ 카카오 '나에게 보내기'는 본인에게만 갑니다. 고객 발송(알림톡)도, 오픈채팅 읽기/쓰기도
   이 API로는 불가능합니다 — 오픈채팅은 공식 API 자체가 없습니다.

⚠️ chatgpt_* 는 OpenAI API를 실제 호출하므로 토큰 비용이 발생합니다.

환경변수:
  KAKAO_REST_API_KEY   카카오 개발자 앱의 REST API 키 (토큰 갱신용)
  KAKAO_ACCESS_TOKEN   talk_message 스코프로 받은 액세스 토큰
  KAKAO_REFRESH_TOKEN  리프레시 토큰 (액세스 토큰 만료 시 자동 갱신)
  OPENAI_API_KEY       OpenAI API 키
  OPENAI_MODEL         기본 모델명 (미설정 시 gpt-4o-mini)

실행:
  python mcp_server.py              # MCP 서버 (stdio)
  python mcp_server.py --selfcheck  # 네트워크 없이 조립 로직만 검증
"""
from __future__ import annotations

import json
import os
import sys
from typing import Literal

import httpx
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from generate_content import build_prompt

mcp = MCPServer("kakao_chatgpt_mcp")

KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
KAKAO_TOKEN_URL = "https://kauth.kakao.com/oauth/token"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_LINK = "https://jasonsjo.github.io/jasons-company/"
MEMO_TEXT_LIMIT = 200  # 카카오 기본 텍스트 템플릿의 text 최대 길이

# ponytail: 갱신된 액세스 토큰은 프로세스 메모리에만 둔다. 서버를 재시작하면
# KAKAO_ACCESS_TOKEN 부터 다시 시작해 만료 시 한 번 더 갱신할 뿐이라 손해가 없다.
# 여러 프로세스가 토큰을 공유해야 할 때만 파일/키체인 저장으로 올릴 것.
_access_token: str | None = None


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ToolError(f"환경변수 {name} 가 설정되어 있지 않습니다.")
    return value


def build_memo_payload(text: str, link_url: str) -> dict:
    """카카오 기본 텍스트 템플릿 조립. 200자 초과는 API가 거부하므로 미리 막는다."""
    if not text.strip():
        raise ToolError("보낼 텍스트가 비어 있습니다.")
    if len(text) > MEMO_TEXT_LIMIT:
        raise ToolError(
            f"카카오 '나에게 보내기' 텍스트는 {MEMO_TEXT_LIMIT}자까지입니다 "
            f"(현재 {len(text)}자). 요약해서 다시 보내세요."
        )
    template = {
        "object_type": "text",
        "text": text,
        "link": {"web_url": link_url, "mobile_web_url": link_url},
    }
    return {"template_object": json.dumps(template, ensure_ascii=False)}


async def _refresh_kakao_token(client: httpx.AsyncClient) -> str:
    resp = await client.post(KAKAO_TOKEN_URL, data={
        "grant_type": "refresh_token",
        "client_id": _require("KAKAO_REST_API_KEY"),
        "refresh_token": _require("KAKAO_REFRESH_TOKEN"),
    })
    if resp.status_code != 200:
        raise ToolError(
            f"카카오 토큰 갱신 실패 ({resp.status_code}): {resp.text}\n"
            "KAKAO_REST_API_KEY / KAKAO_REFRESH_TOKEN 을 확인하세요. "
            "리프레시 토큰도 만료됐다면 talk_message 스코프로 다시 동의받아야 합니다."
        )
    return resp.json()["access_token"]


@mcp.tool(
    name="kakao_send_memo",
    annotations=ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=True),
)
async def kakao_send_memo(text: str, link_url: str = DEFAULT_LINK) -> str:
    """카카오톡 '나에게 보내기'로 메시지를 전송한다 (본인 카톡으로만 감, 최대 200자).

    Args:
        text: 보낼 메시지 본문. 200자 이내.
        link_url: 말풍선을 눌렀을 때 열릴 URL.
    """
    global _access_token
    payload = build_memo_payload(text, link_url)
    if _access_token is None:
        _access_token = _require("KAKAO_ACCESS_TOKEN")

    async with httpx.AsyncClient(timeout=15) as client:
        for attempt in (1, 2):
            resp = await client.post(
                KAKAO_SEND_URL,
                data=payload,
                headers={"Authorization": f"Bearer {_access_token}"},
            )
            if resp.status_code == 401 and attempt == 1:
                _access_token = await _refresh_kakao_token(client)
                continue
            if resp.status_code != 200:
                raise ToolError(f"카카오 전송 실패 ({resp.status_code}): {resp.text}")
            return f"카카오톡 전송 완료 ({len(text)}자)."
    raise ToolError("카카오 전송 실패: 토큰 갱신 후에도 인증되지 않았습니다.")


async def _chatgpt(prompt: str, model: str | None, max_tokens: int) -> str:
    async with httpx.AsyncClient(timeout=180) as client:
        resp = await client.post(
            OPENAI_URL,
            headers={"Authorization": f"Bearer {_require('OPENAI_API_KEY')}"},
            json={
                "model": model or os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
            },
        )
    if resp.status_code != 200:
        raise ToolError(
            f"OpenAI 호출 실패 ({resp.status_code}): {resp.text}\n"
            "모델명이 계정에서 사용 가능한지, OPENAI_API_KEY 가 유효한지 확인하세요."
        )
    return resp.json()["choices"][0]["message"]["content"]


@mcp.tool(
    name="chatgpt_ask",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True),
)
async def chatgpt_ask(prompt: str, model: str | None = None, max_tokens: int = 2000) -> str:
    """ChatGPT에 프롬프트를 보내고 답변을 받는다. 토큰 비용이 발생한다.

    Args:
        prompt: 보낼 프롬프트 전문.
        model: 모델명. 미지정 시 OPENAI_MODEL 환경변수, 그것도 없으면 gpt-4o-mini.
        max_tokens: 응답 최대 토큰.
    """
    return await _chatgpt(prompt, model, max_tokens)


@mcp.tool(
    name="chatgpt_generate_content",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True),
)
async def chatgpt_generate_content(
    industry: Literal["요식업", "병의원", "뷰티", "전문서비스"],
    channel: Literal["blog", "reels", "review"],
    topic: str,
    brand: str = "",
    region: str = "",
    strengths: str = "",
    target: str = "",
    model: str | None = None,
) -> str:
    """업종 가드레일이 적용된 콘텐츠 초안을 ChatGPT로 생성한다. 토큰 비용이 발생한다.

    generate_content.py 의 프롬프트 템플릿(업종별 규제 가드레일 포함)을 그대로 쓴다.
    결과는 사람 검수 전제의 초안이다.

    Args:
        industry: 업종.
        channel: blog(네이버 블로그) | reels(릴스 대본) | review(리뷰 답글).
        topic: 주제/메인 키워드.
        brand: 상호.
        region: 지역.
        strengths: 강점.
        target: 타깃 고객.
        model: 모델명. 미지정 시 OPENAI_MODEL 환경변수.
    """
    prompt = build_prompt({
        "industry": industry, "channel": channel, "topic": topic,
        "brand": brand, "region": region, "strengths": strengths, "target": target,
    })
    return await _chatgpt(prompt, model, 4000)


def selfcheck() -> None:
    """네트워크 없이 조립 로직만 검증."""
    payload = build_memo_payload("테스트", "https://example.com")
    template = json.loads(payload["template_object"])
    assert template["object_type"] == "text"
    assert template["text"] == "테스트"
    assert template["link"]["mobile_web_url"] == "https://example.com"

    for bad in ("", "   ", "가" * (MEMO_TEXT_LIMIT + 1)):
        try:
            build_memo_payload(bad, DEFAULT_LINK)
        except ToolError:
            pass
        else:
            raise AssertionError(f"거부됐어야 하는 입력이 통과함: {bad[:20]!r}")

    prompt = build_prompt({
        "industry": "병의원", "channel": "blog", "topic": "임플란트 과정",
        "brand": "테스트치과",
    })
    assert "의료법 제56조" in prompt, "업종 가드레일이 프롬프트에 없음"
    assert "임플란트 과정" in prompt

    print("selfcheck 통과: 메모 템플릿 조립·길이 검증·가드레일 프롬프트 모두 정상.")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        selfcheck()
    else:
        mcp.run(transport="stdio")
