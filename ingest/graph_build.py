"""개념 목록 + 선수관계 엣지 → engine.ConceptGraph.

레퍼런스(ai-knowledge-graph)에 **없는** 핵심 단계:
  - DAG 강제(순환 제거): 우리 엔진은 순환이면 생성 자체가 실패 (청사진 §3-C, §5-6)
  - 위상 깊이 기반 난이도 부여 (우리 엔진 입력에 필요)
순수 Python — LLM/STT 의존 없음. 단독 테스트 가능.

엣지 방향 규약: (prerequisite, concept) = (from, to). 선수개념 → 후속개념.
"""

from __future__ import annotations

import re
from collections import defaultdict, deque

from engine import Concept, ConceptGraph


def normalize_key(name: str) -> str:
    """표시명은 보존하고 내부 id만 정규화 (한글/대소문자 보존 — 청사진 §5-4).

    공백→밑줄, 소문자화(영문), 양끝 공백 제거. 한글은 그대로 유지된다.
    """
    return re.sub(r"\s+", "_", name.strip().lower())


def break_cycles(nodes: list[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """DFS로 back-edge(순환 유발 엣지)를 찾아 제거 → DAG 보장.

    edges: (prerequisite, concept) = (from=선수, to=후속)
    """
    succ: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:
        succ[a].append(b)

    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    removed: set[tuple[str, str]] = set()

    def dfs(u: str) -> None:
        color[u] = GRAY
        for v in succ[u]:
            if (u, v) in removed:
                continue
            if color[v] == GRAY:        # back-edge = 순환 → 제거
                removed.add((u, v))
            elif color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    # 재귀 깊이 한계 방지를 위해 명시적 스택도 가능하나, 개념 수가 작아 재귀로 충분
    for n in nodes:
        if color[n] == WHITE:
            dfs(n)

    return [(a, b) for (a, b) in edges if (a, b) not in removed]


def assign_difficulty(nodes: list[str], edges: list[tuple[str, str]]) -> dict[str, float]:
    """위상 깊이(=선수개념 사슬 길이)를 0.1~0.9 난이도로 매핑.

    뿌리(선수개념 없음)=쉬움(0.1), 깊을수록 어려움. edges는 DAG여야 함.
    """
    indeg = {n: 0 for n in nodes}
    succ: dict[str, list[str]] = defaultdict(list)
    for a, b in edges:                 # a=prereq → b=concept
        indeg[b] += 1
        succ[a].append(b)

    depth = {n: 0 for n in nodes}
    q = deque([n for n in nodes if indeg[n] == 0])
    while q:
        u = q.popleft()
        for v in succ[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)

    maxd = max(depth.values()) if depth else 0
    maxd = maxd or 1
    return {n: round(0.1 + 0.8 * depth[n] / maxd, 2) for n in nodes}


def build_graph(concept_names: list[str], prereq_edges) -> ConceptGraph:
    """개념명 목록 + 선수관계 엣지 → 검증된 ConceptGraph.

    :param concept_names: 사람이 읽는 개념명 리스트 (중복 허용 — 여기서 합침)
    :param prereq_edges: 객체 리스트. 각 원소는 .concept(후속), .prerequisite(선수)
        속성을 갖거나 (prerequisite, concept) 튜플.
    """
    # 1) 정규화 + 중복 제거 (key 기준, 첫 표시명 보존)
    name_by_key: dict[str, str] = {}
    for nm in concept_names:
        if nm and nm.strip():
            name_by_key.setdefault(normalize_key(nm), nm.strip())
    nodes = list(name_by_key)

    # 2) 엣지를 (prereq_key, concept_key) 로 변환
    raw: list[tuple[str, str]] = []
    for e in prereq_edges:
        if isinstance(e, (tuple, list)):
            prereq, concept = e
        else:
            prereq, concept = e.prerequisite, e.concept
        a, b = normalize_key(prereq), normalize_key(concept)
        # 방어 필터: 목록 밖 개념/자기참조 제거 (청사진 §5-5)
        if a in name_by_key and b in name_by_key and a != b:
            raw.append((a, b))
    raw = list(set(raw))

    # 3) 순환 제거 → DAG (청사진 §5-6)
    dag = break_cycles(nodes, raw)

    # 4) 난이도
    diff = assign_difficulty(nodes, dag)

    # 5) Concept 변환 (prereqs = 그 개념의 선수 key 목록)
    prereqs_of: dict[str, list[str]] = defaultdict(list)
    for a, b in dag:                   # a=prereq → b=concept
        prereqs_of[b].append(a)

    concepts = [
        Concept(id=k, name=name_by_key[k], prereqs=prereqs_of[k], difficulty=diff[k])
        for k in nodes
    ]
    # 생성자에서 _assert_acyclic() 재검증 (이중 안전망)
    return ConceptGraph(concepts)
