"""지역+서비스 글을 CSV로 넣으면, 일마다 무게를 재서 알맞은 모델로 한꺼번에 써 준다.

사용법:
  python write_posts.py posts.csv            # 실제로 생성 (Claude API 호출)
  python write_posts.py posts.csv --dry-run   # 어느 모델이 배정되는지만 확인, 호출 없음

posts.csv 형식 (헤더 포함):
  지역,서비스,요구사항
  강남구,입주청소,
  종로구,사무실청소,법률 사무소 대상이라 신뢰감 있는 전문 톤으로
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

from claude_call import call
from model_router import estimate_weight, load_rules

SYSTEM_PROMPT = (
    "너는 지역 청소 서비스 업체의 블로그 글을 쓰는 카피라이터다. "
    "주어진 지역과 서비스에 맞춰 SEO에 도움이 되는 한국어 소개 글을 800~1200자로 쓴다. "
    "과장 광고 없이 신뢰감 있게, 지역명과 서비스명을 자연스럽게 반복 노출시킨다."
)

OUTPUT_DIR = Path(__file__).parent / "output"


def build_task(region: str, service: str, notes: str) -> str:
    base = f"{region} {service} 서비스 소개 글"
    return f"{base}. 추가 요구사항: {notes}" if notes else base


def build_user_prompt(region: str, service: str, notes: str) -> str:
    prompt = f"지역: {region}\n서비스: {service}"
    if notes:
        prompt += f"\n요구사항: {notes}"
    return prompt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path")
    parser.add_argument("--dry-run", action="store_true", help="모델 배정만 보고 실제 생성은 하지 않는다")
    args = parser.parse_args()

    rules = load_rules()
    rows = list(csv.DictReader(Path(args.csv_path).read_text(encoding="utf-8").splitlines()))

    if not args.dry_run:
        OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"{'지역':<8}{'서비스':<14}{'무게':<8}{'모델':<28}{'사유'}")
    print("-" * 90)

    totals = {"light": 0, "medium": 0, "heavy": 0}
    for row in rows:
        region = row["지역"].strip()
        service = row["서비스"].strip()
        notes = (row.get("요구사항") or "").strip()

        task = build_task(region, service, notes)
        weighed = estimate_weight(task, rules)
        totals[weighed.weight] += 1

        print(f"{region:<8}{service:<14}{weighed.weight:<8}{weighed.model:<28}{weighed.reason}")

        if args.dry_run:
            continue

        result = call(weighed.model, build_user_prompt(region, service, notes), system=SYSTEM_PROMPT)
        out_path = OUTPUT_DIR / f"{region}_{service}.md"
        out_path.write_text(result.text, encoding="utf-8")
        print(f"  -> {out_path} 저장 (input={result.input_tokens}tok, output={result.output_tokens}tok)")

    print("-" * 90)
    print(f"총 {len(rows)}건 — light:{totals['light']}  medium:{totals['medium']}  heavy:{totals['heavy']}")


if __name__ == "__main__":
    main()
