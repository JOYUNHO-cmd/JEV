"""Anthropic Messages API를 직접 호출하는 얇은 래퍼."""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class ClaudeCallError(RuntimeError):
    pass


@dataclass
class Result:
    text: str
    model: str
    input_tokens: int
    output_tokens: int


def call(model: str, user: str, system: str | None = None, max_tokens: int = 1200, api_key: str | None = None) -> Result:
    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ClaudeCallError("ANTHROPIC_API_KEY가 설정돼 있지 않습니다 (.env 확인)")

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        payload["system"] = system

    resp = requests.post(
        API_URL,
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
        json=payload,
        timeout=60,
    )
    if not resp.ok:
        raise ClaudeCallError(f"Claude API 오류 {resp.status_code}: {resp.text}")

    data = resp.json()
    text = "".join(block.get("text", "") for block in data.get("content", []))
    usage = data.get("usage", {})
    return Result(
        text=text,
        model=model,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
    )
