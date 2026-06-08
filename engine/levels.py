"""수준대(audience band) — 같은 엔진을 초등/중고등/대학·성인에 맞게 페이스메이킹.

핵심 원칙: **추천 수학(core.py)은 수준대와 무관하게 보편적이다.**
수준대가 바꾸는 것은 세 가지뿐이다.

  1) 역추적 바닥(floor): 그 수준대가 '이미 안다고 가정'하는 기초 개념.
     → 대학·성인에게 분수의 덧셈까지 거슬러 내려가지 않는다.
     (단, 진단 퀴즈로 실제 결손이 확인되면 가정을 덮어쓴다.)
  2) 그래프 입도(granularity): 영상→개념 생성 시 얼마나 잘게 쪼갤지.
  3) 설명 어투(register): 학습가이드 LLM이 쓰는 말투/용어 수준.

1)은 엔진(LearnerState.assume_known)으로, 2)·3)은 콘텐츠 생성 LLM 프롬프트로 전달된다.
교과목(수학/영어/코딩/역사…)과는 전혀 무관 — 어떤 그래프에도 동일하게 적용된다.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LevelBand:
    key: str
    label: str
    # 이 난이도 이하의 개념은 '이미 안다'고 가정해 역추적 바닥으로 삼는다
    # (진단으로 결손이 드러나면 무효화됨)
    assumed_known_below_difficulty: float
    # 영상→개념 생성 시 권장 입도 (LLM 프롬프트로 전달)
    granularity: str
    # 학습가이드 LLM 어투 (LLM 프롬프트로 전달)
    register: str


ELEMENTARY = LevelBand(
    key="elementary",
    label="초등학생",
    assumed_known_below_difficulty=0.0,   # 아무것도 가정하지 않음 (바닥까지 역추적)
    granularity="아주 잘게. 한 번에 한 가지 작은 개념만.",
    register="짧은 문장, 쉬운 일상어, 구체적 예시와 비유. 한자어·전문용어 지양.",
)

SECONDARY = LevelBand(
    key="secondary",
    label="중·고등학생",
    assumed_known_below_difficulty=0.15,  # 아주 기초적인 것은 안다고 가정
    granularity="단원 수준. 교과 개념 단위로.",
    register="교과서 수준 용어 허용. 원리와 절차를 단계적으로.",
)

TERTIARY_ADULT = LevelBand(
    key="tertiary_adult",
    label="대학생·성인",
    assumed_known_below_difficulty=0.35,  # 기초~중급 전제는 안다고 가정
    granularity="개념 묶음 수준. 압축적으로.",
    register="전문 용어 허용. 압축적·논리 중심. 군더더기 없는 설명.",
)

BANDS = {b.key: b for b in (ELEMENTARY, SECONDARY, TERTIARY_ADULT)}
