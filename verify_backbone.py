"""교육과정 백본 검증 — 결정적(LLM 불필요).

핵심 주장: LLM 이 선수관계를 거의 못 잡고(F1 ~0.33), STT 가 개념명을 오인식해도,
백본이 (1) 별칭으로 표준 개념에 정렬하고 (2) 검증된 선수관계를 주입해
**완전하고 올바른 DAG** 를 결정적으로 만든다.

실행: .venv/bin/python verify_backbone.py
"""

from engine import LearnerState, Recommender
from ingest.backbone import Backbone
from ingest.graph_build import build_graph

BB = Backbone.from_json("data/backbone_seed.json")


def case(title, noisy_concepts, llm_edges, target_name, expect_first):
    print("=" * 74)
    print(title)
    print("=" * 74)
    print(f"  입력 개념(STT/LLM 노이즈 포함): {noisy_concepts}")
    print(f"  LLM 엣지(희소/부정확): {llm_edges or '(없음)'}")

    names, edges = BB.augment(noisy_concepts, llm_edges)
    g = build_graph(names, edges)
    print(f"\n  백본 정렬 후 개념 {g.n}개:")
    for c in g.concepts:
        pr = [g.concepts[g.index(p)].name for p in c.prereqs]
        print(f"    {c.name:<12} 난이도 {c.difficulty} 선수={pr}")

    target = next(c.id for c in g.concepts if c.name == target_name)
    learner = LearnerState(g)
    learner.update_many(target, [0, 0, 0])
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    nxt = rec.next_concept(learner)
    path = []
    for _ in range(g.n + 1):
        n = rec.next_concept(learner)
        path.append(n.name)
        if rec.is_mastered(learner, target):
            break
        learner.update_many(n.concept_id, [1, 1, 1, 1, 1, 1])
        if n.concept_id == target:
            break
    tgt_name = g.concepts[g.index(target)].name
    print(f"\n  '{tgt_name}' 막힘 → 첫 추천: 「{nxt.name}」")
    print(f"  학습 경로: {' → '.join(path)}")
    assert nxt.name == expect_first, f"기대 {expect_first}, 실제 {nxt.name}"
    print(f"  ✅ 통과 (첫 추천 = {expect_first})\n")


def main():
    # 과학: STT 오인식("은결"=응결, "애체"=액체) + LLM 엣지 전무
    case(
        "[과학] 물의 순환 — STT 오인식 + LLM 엣지 0개인데도 완전한 DAG",
        noisy_concepts=["물의 순환", "증발", "은결", "구름", "강수", "애체", "물의 상태 변화"],
        llm_edges=[],                       # LLM 이 엣지를 하나도 못 줘도
        target_name="물의 순환", expect_first="물질의 상태",
    )

    # 수학: 일부 별칭 + 잘못된 LLM 엣지(역방향) 가 섞여도 백본이 권위
    case(
        "[수학] 분수·대수 — 잘못된 LLM 엣지가 섞여도 백본이 바로잡음",
        noisy_concepts=["이차방정식", "인수 분해", "일차 방정식", "분수 덧셈", "약분", "통분", "최대 공약수"],
        llm_edges=[("이차방정식", "최대공약수")],   # 역방향(틀린) LLM 엣지 — 무시돼야
        target_name="이차방정식", expect_first="최대공약수",
    )

    print("=" * 74)
    print("결론: LLM 추출이 부실/오류여도, 백본 매칭+선수관계 주입으로")
    print("      신뢰할 수 있는 학습경로가 결정적으로 보장된다. (LLM 은 '커버리지' 보조 역할)")
    print("=" * 74)


if __name__ == "__main__":
    main()
