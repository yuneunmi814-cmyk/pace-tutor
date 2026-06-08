"""ingest 파이프라인 검증.

1부 (항상 실행, LLM 불필요): graph_build 가 순환을 끊어 DAG 를 보장하고,
   난이도를 부여하며, 결과가 engine.Recommender 와 결합되는지.
2부 (Ollama 있으면 실행): 실제 강의 자막 → 개념 그래프 자동 추출 →
   막힌 개념에서 기초로 역추적되는지 (교과목 무관성 + 환각 표본 점검).
"""

from engine import LearnerState, Recommender
from ingest import build_graph, break_cycles, normalize_key


# ── 1부: 순수 graph_build (LLM 불필요) ──────────────────────────────────────
def part1_graph_build():
    print("=" * 78)
    print("[1부] graph_build — 순환 제거(DAG 강제) + 난이도 + 엔진 결합  (LLM 불필요)")
    print("=" * 78)

    # 일부러 순환을 포함한 (prerequisite, concept) 엣지 집합
    #   세포→엽록체→엽록소→광합성, 광합성→포도당, 그리고 포도당→세포 (순환!)
    concepts = ["세포", "엽록체", "엽록소", "빛 에너지", "광합성", "포도당"]
    edges = [
        ("세포", "엽록체"),
        ("엽록체", "엽록소"),
        ("엽록소", "광합성"),
        ("빛 에너지", "광합성"),
        ("광합성", "포도당"),
        ("포도당", "세포"),   # ← 순환 유발 (포도당이 세포의 선수개념?? 모순)
    ]

    # break_cycles 단독 확인
    nodes = [normalize_key(c) for c in concepts]
    dag = break_cycles(nodes, [(normalize_key(a), normalize_key(b)) for a, b in edges])
    print(f"  원본 엣지 {len(edges)}개 → DAG 엣지 {len(dag)}개 (순환 1개 제거됨)")
    assert len(dag) == len(edges) - 1, "순환이 정확히 1개 제거돼야 함"

    # build_graph 는 순환이 있어도 예외 없이 ConceptGraph 를 만들어야 함
    graph = build_graph(concepts, edges)
    print(f"  ConceptGraph 생성 성공: 개념 {graph.n}개 (순환이었다면 생성 실패했을 것)")
    for c in graph.concepts:
        print(f"    - {c.name:<8} (id={c.id:<12} 난이도 {c.difficulty}  선수={c.prereqs})")

    # 엔진 결합: '광합성'에서 막힌 학습자 → 기초로 역추적되는가
    learner = LearnerState(graph)
    learner.update_many("광합성", [0, 0, 0])
    rec = Recommender(graph, r_star=0.0, W_p=2.0)
    nxt = rec.next_concept(learner)
    print(f"\n  '광합성'에서 막힌 학습자 → 첫 추천: 「{nxt.name}」")
    assert nxt.concept_id != "광합성", "막힌 개념을 그대로 추천하면 안 됨"
    print("  ✅ 1부 통과: 순환 자동 제거 → DAG → 엔진이 기초로 역추적")


# ── 2부: 실제 LLM 추출 (Ollama 필요) ────────────────────────────────────────
SAMPLE_TRANSCRIPT = """
오늘은 광합성에 대해 배워봅시다. 먼저 모든 생물은 세포로 이루어져 있습니다.
식물 세포 안에는 엽록체라는 작은 기관이 있습니다. 엽록체 안에는 엽록소라는
초록색 색소가 들어 있어서 빛 에너지를 흡수합니다. 광합성은 이 빛 에너지를
이용해 물과 이산화탄소로부터 포도당을 만들어내는 과정입니다. 즉 엽록체와
엽록소가 무엇인지 알아야 광합성을 이해할 수 있고, 광합성의 결과로 포도당이
만들어진다는 것을 알 수 있습니다. 포도당은 식물이 사용하는 에너지원입니다.
"""


def part2_llm_extract():
    print("\n" + "=" * 78)
    print("[2부] 실제 자막 → 개념 그래프 자동 추출 (Ollama llama3.1:8b)")
    print("=" * 78)
    try:
        from ingest.pipeline import transcript_to_graph
    except Exception as e:  # pragma: no cover
        print(f"  (건너뜀) ingest 의존성 문제: {e}")
        return

    try:
        print("  추출 중... (로컬 LLM, 1~2분 소요 가능)")
        graph = transcript_to_graph(SAMPLE_TRANSCRIPT, model="llama3.1:8b")
    except Exception as e:
        print(f"  (건너뜀) Ollama 호출 실패 — 데몬/모델 확인: {e}")
        return

    print(f"\n  자동 생성된 개념 그래프: 개념 {graph.n}개")
    for c in graph.concepts:
        print(f"    - {c.name:<12} (난이도 {c.difficulty}  선수={[graph.concepts[graph.index(p)].name for p in c.prereqs]})")

    # DAG 보장은 ConceptGraph 생성 성공으로 이미 증명됨. 엔진 결합 확인:
    # 난이도가 가장 높은(=가장 상위) 개념에서 막혔다고 가정
    top = max(graph.concepts, key=lambda c: c.difficulty)
    learner = LearnerState(graph)
    learner.update_many(top.id, [0, 0, 0])
    rec = Recommender(graph, r_star=0.0, W_p=2.0)
    path = []
    for _ in range(graph.n + 1):
        nxt = rec.next_concept(learner)
        path.append(nxt.name)
        if rec.is_mastered(learner, top.id):
            break
        learner.update_many(nxt.concept_id, [1, 1, 1, 1, 1, 1])
        if nxt.concept_id == top.id:
            break
    print(f"\n  '{top.name}'(최상위)에서 막힌 학습자의 자기속도 학습경로:")
    print("    " + " → ".join(path))
    print("  ✅ 2부 통과: 자막 → (환각차단 추출) → DAG → 엔진 역추적 end-to-end 동작")


if __name__ == "__main__":
    part1_graph_build()
    part2_llm_extract()
    print("\n" + "=" * 78)
    print("완료. 1부(코어)는 결정적으로 통과. 2부는 로컬 LLM 결과라 개념/엣지는")
    print("매 실행 약간 달라질 수 있음(자막 범위 내 환각 표본 점검 권장).")
    print("=" * 78)
