"""다음 학습 추천 — "이 학생이 지금 당장 배울 수 있는 가장 기초 개념".

청사진 §3: substrategy R(약점 보충 수요)이 "모르는 걸 가르쳐라"라고 당기고,
substrategy P(선수개념 준비도)가 "선수개념 안 된 건 아직 하지 마라"라고 막는다.
두 힘이 만나는 지점 = 선수개념은 갖췄으면서 본인은 아직 모르는, 가장 깊은 기초.

모델 단순화(청사진 §5): 개념 1개당 학습활동 1개로 둔다 (Q == K, 활동 i ↔ 개념 i).
따라서 추천 결과 = "다음에 학습할 개념".
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import core
from .concepts import ConceptGraph
from .diagnosis import BKTParams, LearnerState


@dataclass
class Recommendation:
    concept_id: str
    name: str
    score: float
    # 디버깅/학습가이드용 substrategy 분해
    readiness: float    # P — 선수개념 준비도 (낮을수록 준비 안 됨)
    remediation: float  # R — 약점 보충 수요 (높을수록 약점)
    difficulty_fit: float  # D
    mastery: float      # 현재 숙달확률


class Recommender:
    """ConceptGraph 위에서 LearnerState 를 받아 다음 학습 개념을 고른다."""

    def __init__(
        self,
        graph: ConceptGraph,
        bkt: BKTParams | None = None,
        *,
        L_star: float = 2.2,   # 숙달 임계 log-odds (≈ 확률 0.9)
        r_star: float = 0.0,   # 선수개념 관용 임계 (0=엄격; 어린 학습자 권장)
        W_p: float = 2.0,      # readiness 가중 (ALOSI 운영값)
        W_r: float = 1.0,
        W_d: float = 0.5,
        W_c: float = 0.5,
    ):
        self.graph = graph
        self.bkt = bkt or BKTParams()
        self.L_star = L_star
        self.r_star = r_star
        self.W_p, self.W_r, self.W_d, self.W_c = W_p, W_r, W_d, W_c

        K = graph.n
        # 활동 i 는 개념 i 만 다룸 → 대각만 파라미터, 나머지는 NaN(=관련 없음)
        self._guess = np.full((K, K), np.nan)
        self._slip = np.full((K, K), np.nan)
        np.fill_diagonal(self._guess, self.bkt.p_guess)
        np.fill_diagonal(self._slip, self.bkt.p_slip)

        self._prereqs = graph.prereq_matrix()
        self._difficulty = graph.difficulties()

    def _subscores(self, mastery: np.ndarray):
        relevance = core.calculate_relevance(self._guess, self._slip)
        L = np.log(core.odds(mastery))
        difficulty = core.fillna(self._difficulty.astype(float), value=0.5)
        P = core.recommendation_score_P(relevance, L, self._prereqs, self.r_star, self.L_star)
        R = core.recommendation_score_R(relevance, L, self.L_star)
        D = core.recommendation_score_D(relevance, L, difficulty)
        return P, R, D

    def rank(self, learner: LearnerState) -> list[Recommendation]:
        """모든 개념을 추천점수 내림차순으로 정렬해 반환."""
        mastery = learner.mastery_vector()
        scores = core.recommendation_score(
            guess=self._guess,
            slip=self._slip,
            learner_mastery=mastery,
            prereqs=self._prereqs,
            r_star=self.r_star,
            L_star=self.L_star,
            difficulty=self._difficulty,
            W_p=self.W_p, W_r=self.W_r, W_d=self.W_d, W_c=self.W_c,
        )
        P, R, D = self._subscores(mastery)
        recs = []
        for i, c in enumerate(self.graph.concepts):
            recs.append(Recommendation(
                concept_id=c.id, name=c.name, score=float(scores[i]),
                readiness=float(P[i]), remediation=float(R[i]),
                difficulty_fit=float(D[i]), mastery=float(mastery[i]),
            ))
        recs.sort(key=lambda r: r.score, reverse=True)
        return recs

    def next_concept(self, learner: LearnerState) -> Recommendation:
        """지금 학습할 단 하나의 개념."""
        return self.rank(learner)[0]

    def is_mastered(self, learner: LearnerState, concept_id: str) -> bool:
        """log-odds 기준 통달 여부 (L_star 임계)."""
        p = learner.mastery_of(concept_id)
        return float(np.log(core.odds(p))) >= self.L_star
