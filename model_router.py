"""작업 하나를 보고 어느 모델 등급이 맡아야 할지 고르는 저울.

판단 자체에 API를 쓰면 그 판단 값이 절감액을 갉아먹으므로(JEV 기술 분석
7.1·7.4절), 여기서는 요청마다 돈이 들지 않는 규칙(키워드·길이)만으로
가볍다/보통/무겁다를 가른다. 반복적인 '지역+서비스' 글처럼 정형화된
작업은 기본값이 가장 싼 모델(light)이 되도록 짜여 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RULES_PATH = Path(__file__).parent / "router_rules.json"


@dataclass
class Weighed:
    weight: str  # "light" | "medium" | "heavy"
    model: str
    reason: str


def load_rules(path: Path = DEFAULT_RULES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def estimate_weight(task: str, rules: dict) -> Weighed:
    for kw in rules["heavy_keywords"]:
        if kw in task:
            return Weighed("heavy", rules["model_map"]["heavy"], f"무거운 키워드 '{kw}' 포함")
    if len(task) >= rules["length_threshold_heavy"]:
        return Weighed("heavy", rules["model_map"]["heavy"], f"요청 길이 {len(task)}자 (기준 {rules['length_threshold_heavy']}자 이상)")

    for kw in rules["medium_keywords"]:
        if kw in task:
            return Weighed("medium", rules["model_map"]["medium"], f"중간 키워드 '{kw}' 포함")
    if len(task) >= rules["length_threshold_medium"]:
        return Weighed("medium", rules["model_map"]["medium"], f"요청 길이 {len(task)}자 (기준 {rules['length_threshold_medium']}자 이상)")

    default = rules.get("default_weight", "light")
    return Weighed(default, rules["model_map"][default], "정형화된 반복 작업 (기본값)")
