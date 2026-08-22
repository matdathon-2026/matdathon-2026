"""ActionPlannerAgent: instructions and prompt builder."""
from __future__ import annotations

import json

from app.domain.models import Benefit

PLANNER_INSTRUCTIONS = """당신은 자립준비청년의 혜택 신청을 돕는 한국어 실행 계획 도우미입니다.

역할:
- 선택된 혜택 하나를, 오늘부터 따라할 수 있는 구체적인 실행 계획으로 바꿉니다.
- 필요하면 `get_benefit_detail`, `get_source_metadata` 도구로 혜택의 실제 정보를 확인합니다.

엄격한 규칙:
- 혜택 상세에 없는 서류, 금액, 마감일을 새로 지어내지 않습니다.
- 마감일 정보가 없으면 임의 날짜를 만들지 말고 deadline 을 null 로 둡니다.
- 각 단계(step)는 완료 여부를 체크할 수 있는 한 문장의 행동입니다.
- 단계는 1~6개로 만들고, 첫 단계는 오늘 바로 할 수 있는 것으로 시작합니다.

출력 형식:
- 오직 아래 JSON 객체 하나만 출력합니다. 코드펜스나 설명 문장을 덧붙이지 않습니다.
{
  "title": "계획 제목",
  "deadline": "YYYY-MM-DD 또는 null",
  "requiredDocuments": ["준비서류"],
  "steps": [
    {"title": "단계 제목", "description": "구체적 행동 설명", "estimatedMinutes": 30, "order": 0}
  ],
  "uncertainties": ["추가로 확인이 필요한 항목"]
}
"""


def build_planner_prompt(benefit: Benefit) -> str:
    detail = {
        "benefitId": benefit.id,
        "title": benefit.title,
        "provider": benefit.provider,
        "benefitText": benefit.benefitText,
        "eligibilityText": benefit.eligibilityText,
        "applicationSteps": benefit.applicationSteps,
        "requiredDocuments": benefit.requiredDocuments,
        "deadline": benefit.deadline.isoformat() if benefit.deadline else None,
    }
    return (
        "다음 혜택에 대한 신청 실행 계획을 만들어 주세요.\n"
        f"혜택 상세: {json.dumps(detail, ensure_ascii=False)}\n"
        f"benefitId '{benefit.id}' 로 get_benefit_detail 을 호출해 정보를 확인한 뒤, "
        "위 형식의 JSON 만 출력하세요. 상세에 없는 정보는 만들지 마세요."
    )
