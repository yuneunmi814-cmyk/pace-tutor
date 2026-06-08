"""입력 기반 선수관계 구조 — 미리 짠 백본 없이 '자료 자체'에서 순서를 끌어낸다.

배경(사용자 지적): 자료 기반 학습인데 왜 개념을 미리 짜나? → 개념·진단은 이미 자료/응답
기반이고, '선수관계 구조'만 약한 로컬LLM 때문에 백본에 기댔다. 여기서는 구조도 자료에서 뽑는다.

두 가지 방법(어느 게 신뢰할 만한지는 eval_structure.py로 측정):
  A. order_by_transcript — 강의는 보통 선수개념을 먼저 설명한다 → 자막 첫 등장 순서(결정적)
  B. order_by_llm       — LLM에 약한 '관계 추출' 대신 쉬운 '기초→고급 정렬'을 시킴

둘 다 '순서'를 만들고 chain_edges 로 인접 쌍을 선수관계 엣지로 만든다.
순서 기반이라 엣지가 항상 앞→뒤 = **순환이 구조적으로 불가능**(DAG 보장).
한계: 선형 사슬이라 '여러 선수개념'(이차방정식 ← 인수분해 AND 일차방정식)은 표현 못함
      → 백본 오버레이가 있으면 그런 병렬 구조·자료에 없는 기초까지 보완.
"""

from __future__ import annotations

import re

from ollama import chat
from pydantic import BaseModel

from .extract import DEFAULT_MODEL


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().lower())


def first_mention_index(text: str, name: str) -> int:
    """자막에서 개념이 처음 등장하는 위치(문자 인덱스). 없으면 큰 값(=뒤로)."""
    t = text.lower()
    i = t.find(name.lower())
    if i >= 0:
        return i
    # 정확히 못 찾으면 개념명의 토큰 중 가장 먼저 나오는 위치
    toks = [w for w in re.split(r"\s+", name) if len(w) > 1]
    idxs = [t.find(w.lower()) for w in toks if t.find(w.lower()) >= 0]
    return min(idxs) if idxs else len(text) + 1


def order_by_transcript(concepts: list[str], text: str) -> list[str]:
    """자막 첫 등장 순서로 개념 정렬(기초가 먼저 나온다는 가정)."""
    return sorted(concepts, key=lambda c: first_mention_index(text, c))


class _Ordered(BaseModel):
    ordered: list[str]


ORDER_SYS = (
    "너는 학습 개념들을 가장 기초적인 것부터 가장 고급인 것 순서로 정렬하는 도구다. "
    "먼저 알아야 하는(선수) 개념이 앞에 오도록 한다. "
    "주어진 개념만 사용하고, 하나도 빠뜨리지 말고 모두 포함한다. 자막의 언어를 따른다."
)


def order_by_llm(concepts: list[str], model: str = DEFAULT_MODEL) -> list[str]:
    """LLM에 '기초→고급 정렬'을 시킴(관계 추출보다 쉬운 과제). 결과를 알려진 집합으로 정제."""
    if len(concepts) < 2:
        return list(concepts)
    listing = "\n".join(f"- {c}" for c in concepts)
    r = chat(
        model=model,
        messages=[
            {"role": "system", "content": ORDER_SYS},
            {"role": "user", "content": f"개념 목록:\n{listing}\n\n기초→고급 순서로 정렬하라."},
        ],
        format=_Ordered.model_json_schema(),
        options={"temperature": 0},
    )
    out = _Ordered.model_validate_json(r.message.content).ordered
    by = {_norm(c): c for c in concepts}
    ordered, used = [], set()
    for o in out:
        k = _norm(o)
        if k in by and k not in used:
            ordered.append(by[k]); used.add(k)
    for c in concepts:                       # 누락된 개념은 뒤에 붙임
        if _norm(c) not in used:
            ordered.append(c)
    return ordered


def chain_edges(ordered: list[str]) -> list[tuple[str, str]]:
    """정렬된 개념 → 인접 선수관계 엣지 (prereq=앞, concept=뒤). 항상 DAG."""
    return [(ordered[i], ordered[i + 1]) for i in range(len(ordered) - 1)]
