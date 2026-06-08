"""개념 노드 + 선수개념 DAG.

ALOSI의 prereqs 행렬을 우리 도메인 용어로 감싼다.
prereqs[i][j] = 1  ⇔  개념 i 는 개념 j 의 선수개념 (행=선수, 열=후속).
이 방향성은 청사진 §6-1 의 함정 — 뒤집으면 역추적이 거꾸로 동작한다.
그래프는 반드시 DAG (순환 금지) 여야 한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np


@dataclass
class Concept:
    """학습 개념 노드.

    :param id: 고유 키 (예: "gcd")
    :param name: 사람이 읽는 이름 (예: "최대공약수")
    :param prereqs: 이 개념의 직접 선수개념 id 목록
    :param difficulty: 0.0(쉬움)~1.0(어려움) 난이도
    :param grade: 표준 학년/단계 라벨 (선택, 표시용)
    """

    id: str
    name: str
    prereqs: list[str] = field(default_factory=list)
    difficulty: float = 0.5
    grade: str = ""


class ConceptGraph:
    """개념 집합 + 선수관계 행렬을 관리. 생성 시 DAG 검증."""

    def __init__(self, concepts: Iterable[Concept]):
        self.concepts: list[Concept] = list(concepts)
        self.ids: list[str] = [c.id for c in self.concepts]
        self._index: dict[str, int] = {cid: i for i, cid in enumerate(self.ids)}

        unknown = {p for c in self.concepts for p in c.prereqs if p not in self._index}
        if unknown:
            raise ValueError(f"알 수 없는 선수개념 참조: {sorted(unknown)}")

        self._assert_acyclic()

    @property
    def n(self) -> int:
        return len(self.concepts)

    def index(self, concept_id: str) -> int:
        return self._index[concept_id]

    def prereq_matrix(self) -> np.ndarray:
        """KxK numpy 행렬. [i][j]=1 ⇔ i는 j의 선수개념 (행=선수, 열=후속)."""
        K = self.n
        m = np.zeros((K, K), dtype=float)
        for c in self.concepts:
            j = self._index[c.id]
            for p in c.prereqs:
                i = self._index[p]
                m[i][j] = 1.0
        return m

    def difficulties(self) -> np.ndarray:
        return np.array([c.difficulty for c in self.concepts], dtype=float)

    def _assert_acyclic(self) -> None:
        """위상정렬 시도로 순환 탐지 (Kahn)."""
        indeg = {cid: 0 for cid in self.ids}
        for c in self.concepts:
            indeg[c.id] += len(c.prereqs)
        # 후속 목록
        successors: dict[str, list[str]] = {cid: [] for cid in self.ids}
        for c in self.concepts:
            for p in c.prereqs:
                successors[p].append(c.id)

        queue = [cid for cid, d in indeg.items() if d == 0]
        visited = 0
        while queue:
            cur = queue.pop()
            visited += 1
            for s in successors[cur]:
                indeg[s] -= 1
                if indeg[s] == 0:
                    queue.append(s)
        if visited != self.n:
            raise ValueError("선수개념 그래프에 순환이 있습니다 (DAG가 아님).")
