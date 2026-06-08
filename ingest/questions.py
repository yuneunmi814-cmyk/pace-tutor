"""개념별 진단 문항 생성 (Ollama 제약 디코딩).

진단 퀴즈 응답이 engine.LearnerState.update() 로 들어가 숙달도를 갱신한다.
문항은 약간의 다양성을 위해 temperature=0.3.
"""

from __future__ import annotations

from ollama import chat
from pydantic import BaseModel

from .extract import DEFAULT_MODEL


class Question(BaseModel):
    stem: str
    choices: list[str]
    answer_index: int


class QuestionSet(BaseModel):
    questions: list[Question]


QUESTION_SYS = (
    "개념 하나의 숙달 여부를 가릴 4지선다 진단 문항을 만든다. "
    "정답은 정확히 1개. 보기에는 그럴듯한 오답을 포함한다. "
    "참고 자막의 범위를 벗어나지 마라. 자막의 언어를 따른다."
)


def make_questions(concept_name: str, transcript_excerpt: str = "",
                   n: int = 3, model: str = DEFAULT_MODEL) -> list[Question]:
    ref = f"\n참고 자막:\n{transcript_excerpt}" if transcript_excerpt else ""
    r = chat(
        model=model,
        messages=[
            {"role": "system", "content": QUESTION_SYS},
            {"role": "user", "content": f"개념: {concept_name}{ref}\n진단 문항 {n}개를 만들어라."},
        ],
        format=QuestionSet.model_json_schema(),
        options={"temperature": 0.3},
    )
    return QuestionSet.model_validate_json(r.message.content).questions
