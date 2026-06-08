"""pace-tutor 진단 엔진 — 개념별 수준진단 + 선수개념 역추적.

핵심 알고리즘은 청사진(prerequisite-diagnosis-reference.md) 참조:
  - 숙달도 추정: Bayesian Knowledge Tracing (diagnosis.py)
  - 선수개념 역추적 추천: ALOSI substrategy P/R/C/D (core.py, recommender.py)
"""

from .concepts import Concept, ConceptGraph
from .diagnosis import LearnerState
from .recommender import Recommender, Recommendation
from .levels import LevelBand, ELEMENTARY, SECONDARY, TERTIARY_ADULT, BANDS

__all__ = [
    "Concept",
    "ConceptGraph",
    "LearnerState",
    "Recommender",
    "Recommendation",
    "LevelBand",
    "ELEMENTARY",
    "SECONDARY",
    "TERTIARY_ADULT",
    "BANDS",
]
