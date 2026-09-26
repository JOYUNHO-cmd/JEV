"""메일처럼 여러 건을 한꺼번에 넣으면, 급한 정도와 갈래를 갈라 준다.

판단만 하는 좁은 작업이라 가장 싼 모델(Haiku) 하나로, 여러 건을 한 요청에
묶어 보낸다 (JEV 기술 분석 3.3절 '물음 여러 개를 한 번에 묻기'와 같은 발상 —
단, 실제 Jev API 대신 Claude에게 JSON 스키마를 직접 지시해서 구현한다).

사용법:
  python triage_bulk.py mails.txt
  python triage_bulk.py mails.txt --categories "환불,불만,단순문의,광고/스팸,협업제안"

mails.txt 형식: 건마다 빈 줄로 구분.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from claude_call import call

MODEL = "claude-haiku-4-5-20251001"
DEFAULT_CATEGORIES = ["환불/결제", "불만/컴플레인", "단순 문의", "광고/스팸", "협업/제휴 제안"]

URGENCY_ORDER = {"긴급": 0, "보통": 1, "낮음": 2}


def split_items(text: str) -> list[str]:
    items = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    return items


def build_prompt(items: list[str], categories: list[str]) -> str:
    numbered = "\n".join(f"[{i}] {item}" for i, item in enumerate(items))
    cat_list = ", ".join(categories)
    return (
        f"아래 {len(items)}건의 글을 각각 판정해라. 갈래는 다음 중 하나로 고정한다: {cat_list}, 기타.\n"
        "급한 정도는 '긴급'/'보통'/'낮음' 중 하나로 고른다. 돈이 걸려 있거나 즉시 조치가 필요하면 긴급이다.\n"
        "각 항목마다 정확히 이 JSON 배열 형식으로만 답하고 다른 말은 쓰지 마라:\n"
        '[{"id": 0, "category": "...", "urgency": "...", "reason": "짧은 한 줄 근거"}, ...]\n\n'
        f"{numbered}"
    )


def parse_answers(raw_text: str) -> list[dict]:
    match = re.search(r"\[.*\]", raw_text, re.DOTALL)
    if not match:
        raise ValueError(f"JSON 배열을 찾지 못함: {raw_text[:200]}")
    return json.loads(match.group(0))


def triage(items: list[str], categories: list[str] | None = None) -> list[dict]:
    categories = categories or DEFAULT_CATEGORIES
    prompt = build_prompt(items, categories)
    result = call(MODEL, prompt, max_tokens=2000)
    answers = parse_answers(result.text)
    for a in answers:
        a["text"] = items[a["id"]]
    return answers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--categories", default=",".join(DEFAULT_CATEGORIES))
    args = parser.parse_args()

    categories = [c.strip() for c in args.categories.split(",")]
    items = split_items(Path(args.path).read_text(encoding="utf-8"))
    print(f"{len(items)}건 로드, {MODEL} 한 번 호출로 일괄 판정합니다.\n")

    answers = triage(items, categories)
    answers.sort(key=lambda a: URGENCY_ORDER.get(a["urgency"], 9))

    for a in answers:
        preview = a["text"][:40].replace("\n", " ")
        print(f"[{a['urgency']:<4}][{a['category']:<10}] {preview}...  — {a['reason']}")


if __name__ == "__main__":
    main()
