"""입력 기반 구조 추출 품질 측정 — 순서 정확도(ordering accuracy).

지표: 골드 선수쌍 (a→b: a를 b보다 먼저 배워야 함)에 대해, 추출된 순서가 a를 b보다
앞에 두는 비율. 1.0이면 모든 선수관계를 순서가 존중함.

비교:
  - transcript : 자막 첫 등장 순서 (결정적)
  - llm-order  : LLM 기초→고급 정렬
  - llm-edges  : (기존) LLM 관계 추출 → 위상순서  [참고용]
Ollama 필요(llm-* 항목).
"""

from ingest.structure import order_by_transcript, order_by_llm
from ingest.extract import extract_prereqs

MODEL = "llama3.1:8b"

# 자막 있는 과목(물의 순환) — transcript / llm-order 둘 다 측정
WATER_TEXT = (
    "오늘은 물의 순환에 대해 배워보겠습니다. 물은 고체, 액체, 기체 세 가지 상태로 존재합니다. "
    "태양이 물을 데우면 증발이 일어나고, 수증기가 식으면 응결이 됩니다. 응결로 구름이 생기고, "
    "구름에서 비나 눈이 내리는 강수가 일어납니다. 물의 순환을 이해하려면 먼저 물의 상태 변화를 알아야 합니다."
)
WATER = {
    "concepts": ["물의 순환", "물의 상태", "증발", "응결", "구름", "강수"],
    "text": WATER_TEXT,
    # 골드 선수쌍 (먼저 → 나중)
    "gold": [("물의 상태", "증발"), ("물의 상태", "응결"), ("증발", "물의 순환"),
             ("응결", "구름"), ("구름", "강수"), ("강수", "물의 순환")],
}

CODING = {
    "concepts": ["변수", "자료형", "연산자", "조건문", "반복문", "함수", "재귀"],
    "text": None,
    "gold": [("변수", "자료형"), ("자료형", "연산자"), ("연산자", "조건문"),
             ("조건문", "반복문"), ("반복문", "함수"), ("함수", "재귀")],
}


def order_accuracy(order: list[str], gold) -> float:
    idx = {c: i for i, c in enumerate(order)}
    ok = sum(1 for a, b in gold if idx.get(a, 1e9) < idx.get(b, -1))
    return ok / len(gold)


def edges_to_order(concepts, edges):
    """LLM 관계 엣지를 위상정렬로 순서화(비교용). 순환이면 부분만."""
    from collections import defaultdict, deque
    succ = defaultdict(list); indeg = {c: 0 for c in concepts}
    eset = {(a, b) for a, b in [(e.prerequisite, e.concept) for e in edges]
            if a in indeg and b in indeg}
    for a, b in eset:
        succ[a].append(b); indeg[b] += 1
    q = deque([c for c in concepts if indeg[c] == 0]); out = []
    while q:
        u = q.popleft(); out.append(u)
        for v in succ[u]:
            indeg[v] -= 1
            if indeg[v] == 0: q.append(v)
    for c in concepts:                      # 남은(순환 관여) 개념 뒤에 붙임
        if c not in out: out.append(c)
    return out


def main():
    print("=" * 74)
    print("입력 기반 구조 — 순서 정확도(높을수록 선수관계를 잘 존중)")
    print("=" * 74)

    print("\n[물의 순환]  (자막 있음)")
    t_order = order_by_transcript(WATER["concepts"], WATER["text"])
    print(f"  transcript 순서: {t_order}")
    print(f"    정확도: {order_accuracy(t_order, WATER['gold']):.2f}")
    l_order = order_by_llm(WATER["concepts"], MODEL)
    print(f"  llm-order  순서: {l_order}")
    print(f"    정확도: {order_accuracy(l_order, WATER['gold']):.2f}")
    e_order = edges_to_order(WATER["concepts"], extract_prereqs(WATER["concepts"], MODEL))
    print(f"    llm-edges 정확도(참고): {order_accuracy(e_order, WATER['gold']):.2f}")

    print("\n[코딩]  (자막 없음 → llm-order)")
    l_order = order_by_llm(CODING["concepts"], MODEL)
    print(f"  llm-order  순서: {l_order}")
    print(f"    정확도: {order_accuracy(l_order, CODING['gold']):.2f}")
    e_order = edges_to_order(CODING["concepts"], extract_prereqs(CODING["concepts"], MODEL))
    print(f"    llm-edges 정확도(참고): {order_accuracy(e_order, CODING['gold']):.2f}")

    print("\n" + "=" * 74)
    print("해석: 순서 정확도가 높은 방법을 자료기반 구조의 기본으로 채택.")
    print("백본이 있으면 이 위에 병렬구조·자료에 없는 기초를 덧입힌다(오버레이).")
    print("=" * 74)


if __name__ == "__main__":
    main()
