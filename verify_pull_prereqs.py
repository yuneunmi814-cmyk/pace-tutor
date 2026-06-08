"""Below-material prerequisite pulling — deterministic (no LLM).

The original motivation: a 9th grader stuck on quadratics is often missing an
elementary fraction concept the quadratics lecture never mentions. A material-only
graph can't route there (the concept isn't in the material). The backbone overlay
pulls those assumed-but-untaught prerequisites into the graph so the learner can be
diagnosed and routed all the way down to the real gap.
"""

import glob
from engine import LearnerState, Recommender
from ingest.backbone import Backbone
from ingest.graph_build import build_graph

BB = Backbone.from_jsons(sorted(glob.glob("data/backbone_*.json")))


def main():
    print("=" * 74)
    print("자료에 없는 하위 선수개념 끌어오기 (pull_prereqs)")
    print("=" * 74)

    # 강의가 다룬 것: '이차방정식' 단 하나 (분수·약분은 강의에 안 나옴)
    material = ["이차방정식"]
    print(f"\n강의가 다룬 개념: {material}")

    added = BB.pulled_prereqs(material)
    print(f"백본이 끌어온 '안 가르친 기초': {added}")
    assert "최대공약수" in added and "분수의 덧셈" in added, added

    names, edges = BB.augment(material, [], pull_prereqs=True)
    g = build_graph(names, edges)
    print(f"\n최종 그래프 {g.n}개 (강의 1개 + 끌어온 {g.n-1}개):")
    for c in sorted(g.concepts, key=lambda c: c.difficulty):
        pr = [g.concepts[g.index(p)].name for p in c.prereqs]
        print(f"  {c.name:<10} 난이도 {c.difficulty} 선수={pr}")

    # 학습자: 이차방정식 막힘 + (자료에 없던) 분수의 덧셈도 모름 → 거기까지 역추적되나?
    learner = LearnerState(g)
    learner.update_many("이차방정식", [0, 0, 0])
    learner.update_many("분수의_덧셈", [0, 0, 0])   # 진짜 구멍은 분수
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    nxt = rec.next_concept(learner)
    print(f"\n'이차방정식'에서 막혔고 분수도 약한 학습자 → 첫 추천: 「{nxt.name}」")
    assert nxt.name == "최대공약수", nxt.name

    # 대조: pull 끄면 강의 범위(이차방정식 하나)뿐 → 기초로 못 내려감
    n2, e2 = BB.augment(material, [], pull_prereqs=False)
    g2 = build_graph(n2, e2)
    print(f"\n[대조] pull 끔 → 그래프 {g2.n}개: {[c.name for c in g2.concepts]}")
    assert g2.n == 1

    print("\n" + "=" * 74)
    print("✅ 강의가 '이차방정식'만 다뤄도, 강의가 전제한 분수·최대공약수까지 끌어와")
    print("   진단하고 '아주 기본부터' 역추적한다 — 처음 목표(중3→초등 결손)를 완성.")
    print("=" * 74)


if __name__ == "__main__":
    main()
