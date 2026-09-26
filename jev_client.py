"""Jev(System One Model) API 클라이언트.

TypeSafe AI의 Jev API에 state·questions를 보내고 answers를 받는다.
https://docs.typesafe.ai/api
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()


class JevError(RuntimeError):
    pass


@dataclass
class JevClient:
    api_key: str | None = None
    model: str = os.environ.get("TYPESAFE_MODEL", "jev-1.13.0")
    base_url: str = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai/v1")
    timeout: float = 15.0

    def __post_init__(self) -> None:
        self.api_key = self.api_key or os.environ.get("TYPESAFE_API_KEY")
        if not self.api_key:
            raise JevError("TYPESAFE_API_KEY가 설정돼 있지 않습니다 (.env 확인)")

    def judge(self, state: dict[str, Any], questions: dict[str, Any], model: str | None = None) -> dict[str, Any]:
        """state와 questions를 한 요청으로 묶어 보내고 answers를 반환한다 (3.3절 병렬 처리)."""
        resp = requests.post(
            f"{self.base_url}/systemone",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model or self.model,
                "state": state,
                "questions": questions,
            },
            timeout=self.timeout,
        )
        if not resp.ok:
            raise JevError(f"Jev API 오류 {resp.status_code}: {resp.text}")
        return resp.json()["answers"]
