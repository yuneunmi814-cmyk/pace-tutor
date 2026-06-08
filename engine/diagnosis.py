"""수준진단 — 개념별 숙달확률을 Bayesian Knowledge Tracing 으로 추적.

청사진 §4 는 운영 단계에서 pyBKT 의 Roster API 를 권장한다. 다만 pyBKT 는
네이티브 빌드 의존성이 무거워(청사진 §6-6) 콜드스타트/검증 단계에서는
동일한 BKT 업데이트 식(core.calculate_mastery_update 과 수학적으로 동일)을
개념 단위로 직접 구현한다. 나중에 LearnerState 를 pyBKT Roster 어댑터로
교체해도 외부 인터페이스(update / mastery_vector)는 동일하게 유지된다.

표준 BKT 파라미터 (개념별, 청사진 §6-2):
  - p_guess  : 모르는데 맞출 확률 (기본 0.20)
  - p_slip   : 아는데 틀릴 확률  (기본 0.10)
  - p_transit: 한 번 풀고 새로 학습될 확률 (기본 0.10)
  - p_prior  : 사전 숙달확률 (기본 0.10)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .concepts import ConceptGraph


@dataclass
class BKTParams:
    p_guess: float = 0.20
    p_slip: float = 0.10
    p_transit: float = 0.10
    p_prior: float = 0.10

    def __post_init__(self):
        # degeneracy 방지 (청사진 §6-3): guess<0.5, slip<0.5, guess+slip<1
        if not (self.p_guess < 0.5 and self.p_slip < 0.5 and self.p_guess + self.p_slip < 1.0):
            raise ValueError(
                "BKT degeneracy: guess/slip 은 각각 0.5 미만, 합도 1 미만이어야 함"
            )


class LearnerState:
    """한 학습자의 개념별 숙달확률 벡터를 들고 다니며 응답마다 갱신."""

    def __init__(self, graph: ConceptGraph, params: BKTParams | None = None):
        self.graph = graph
        self.params = params or BKTParams()
        # 모든 개념을 사전확률로 초기화
        self._mastery = np.full(graph.n, self.params.p_prior, dtype=float)

    def mastery_vector(self) -> np.ndarray:
        """추천 엔진에 넣을 1xK 숙달 **확률** 벡터."""
        return self._mastery.copy()

    def assume_known(self, concept_ids, p: float = 0.99) -> None:
        """수준대(audience band)의 '이미 안다고 가정'하는 바닥 개념을 사전 주입.

        예) 대학·성인에게는 초등 기초를 안다고 가정해 거기까지 역추적하지 않음.
        진단 퀴즈에서 실제 결손이 드러나면 update()가 이 가정을 덮어쓴다.
        """
        for cid in concept_ids:
            self._mastery[self.graph.index(cid)] = p

    def apply_level_floor(self, band) -> list[str]:
        """LevelBand 의 난이도 바닥을 적용해 그 이하 개념을 '안다'고 가정.

        :return: 가정된(=바닥으로 깐) 개념 id 목록
        """
        floor = [c.id for c in self.graph.concepts
                 if c.difficulty <= band.assumed_known_below_difficulty]
        self.assume_known(floor)
        return floor

    def mastery_of(self, concept_id: str) -> float:
        return float(self._mastery[self.graph.index(concept_id)])

    def update(self, concept_id: str, correct: bool | int | float) -> float:
        """개념에 대한 한 문항 응답으로 숙달확률을 베이지안 갱신.

        :param correct: 1=정답, 0=오답 (0.0~1.0 부분점수도 허용)
        :return: 갱신된 숙달확률
        """
        i = self.graph.index(concept_id)
        p = self._mastery[i]
        g, s, t = self.params.p_guess, self.params.p_slip, self.params.p_transit

        score = float(correct)
        # 증거 반영 (정답/오답 가중 혼합 — 부분점수 지원)
        p_correct_evidence = p * (1 - s) / (p * (1 - s) + (1 - p) * g)
        p_incorrect_evidence = p * s / (p * s + (1 - p) * (1 - g))
        p_evidence = score * p_correct_evidence + (1 - score) * p_incorrect_evidence
        # 학습 전이 (풀이 과정에서 새로 학습될 가능성)
        p_new = p_evidence + (1 - p_evidence) * t

        self._mastery[i] = p_new
        return float(p_new)

    def update_many(self, concept_id: str, responses) -> float:
        """같은 개념의 여러 응답을 순차 반영. responses: iterable of 0/1."""
        last = self.mastery_of(concept_id)
        for r in responses:
            last = self.update(concept_id, r)
        return last
