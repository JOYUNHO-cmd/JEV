"""고객 문의 분류 + 라우팅 데모 (JEV 기술 분석 2.3~2.4, 7.5절 구현).

의미 판단(Jev)과 사실 확인(코드/DB)을 분리한다: Jev는 고객 메시지에서
'무슨 요청인지'와 '환불 확률'만 답하고, 중복 거래 여부·승인 권한 같은
사실은 별도 시스템에서 조회한다는 전제를 그대로 따른다 (5.2절).
"""
from __future__ import annotations

from typing import Any

from jev_client import JevClient

QUESTIONS = {
    "request_type": {
        "type": "choice",
        "instructions": "message에 나타난 고객의 현재 요청을 분류하세요.",
        "criteria": {
            "refund": "이미 결제한 금액을 돌려받으려는 요청",
            "billing_history": "과거 결제 기록을 조회하려는 요청",
            "other": "요청 내용은 명확하지만 환불이나 결제 기록 조회가 아님",
            "unknown": "요청을 분류할 정보가 부족하거나 내용이 모호함",
        },
    },
    "refund_requested": {
        "type": "noul",
        "instructions": "message가 실제로 환불을 요청하는 문장인지 판단하세요. 환불이 필요 없다는 부정 표현이면 낮은 확률을 반환하세요.",
    },
}

# 라우팅 정책: negative_threshold < positive_threshold 여야 한다 (7.5절)
POLICY = {"neg": 0.2, "pos": 0.8}

NEXT_BY_FACT = [
    ("transaction_data_complete", "fetch_missing_records"),
    ("verified_duplicate_charge", "review_transaction"),
    ("refund_within_authority", "request_authorized_review"),
]


def fetch_facts(message: str) -> dict[str, bool]:
    """실제 거래 조회 대신 쓰는 자리표시자. 운영에서는 DB/결제 API로 대체해야 한다."""
    return {
        "transaction_data_complete": True,
        "verified_duplicate_charge": True,
        "refund_within_authority": True,
    }


def route(answers: dict[str, Any], facts: dict[str, bool], policy: dict[str, float]) -> str:
    p = answers["refund_requested"]["noul"]

    if p <= policy["neg"]:
        return "use_other_workflow"
    if p < policy["pos"]:
        return "clarify_request"

    for key, step in NEXT_BY_FACT:
        if not facts[key]:
            return step
    return "prepare_refund_for_execution_checks"


def classify(client: JevClient, message: str) -> dict[str, Any]:
    return client.judge(state={"message": message}, questions=QUESTIONS)


def main() -> None:
    client = JevClient()
    messages = [
        "환불은 필요 없고, 지난달 결제 내역만 확인하고 싶습니다.",
        "같은 주문으로 돈이 두 번 나갔습니다. 하나는 돌려주세요.",
        "지난번에 말씀드린 그 건, 그냥 처리해 주세요.",
    ]

    for message in messages:
        answers = classify(client, message)
        facts = fetch_facts(message)
        next_step = route(answers, facts, POLICY)

        request_type = answers["request_type"]
        refund_p = answers["refund_requested"]["noul"]
        print(f"메시지: {message}")
        print(f"  request_type = {request_type['choice']} (p={request_type['probabilities'][request_type['choice']]:.2f})")
        print(f"  refund_requested = {refund_p:.2f}")
        print(f"  next_step = {next_step}")
        print()


if __name__ == "__main__":
    main()
