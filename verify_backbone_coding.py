"""Programming/coding backbone verification — deterministic (no LLM).

Confirms the coding curriculum (English + Korean) produces a correct prerequisite
DAG, back-tracks from an advanced topic to the deepest foundation, and serves
curated quiz questions with trusted keys — same reliability as math/science.
"""

import glob
from engine import LearnerState, Recommender
from ingest.backbone import Backbone
from ingest.graph_build import build_graph

BB = Backbone.from_jsons(sorted(glob.glob("data/backbone_*.json")))


def path_for(noisy_concepts, target_name):
    names, edges = BB.augment(noisy_concepts, [], fuzzy=True)
    g = build_graph(names, edges)
    target = next(c.id for c in g.concepts if c.name == target_name)
    learner = LearnerState(g)
    learner.update_many(target, [0, 0, 0])
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    first = rec.next_concept(learner).name
    path = []
    for _ in range(g.n + 1):
        n = rec.next_concept(learner); path.append(n.name)
        if rec.is_mastered(learner, target): break
        learner.update_many(n.concept_id, [1, 1, 1, 1, 1, 1])
        if n.concept_id == target: break
    return g, first, path


def main():
    print("=" * 74)
    print(f"Coding backbone — merged {len(BB.concepts)} concepts across subjects/langs")
    print("=" * 74)

    # English: stuck on recursion (via aliases) → must start at Variables
    g, first, path = path_for(
        ["recursive functions", "functions", "loops", "conditionals", "operators",
         "data types", "variables"],
        "Recursion",
    )
    print("\n[EN] stuck on Recursion")
    print("  first:", first)
    print("  path :", " → ".join(path))
    assert first == "Variables", first

    # Korean: stuck on 재귀 → must start at 변수
    g, first, path = path_for(
        ["재귀 함수", "함수", "반복문", "조건문", "연산자", "자료형", "변수"],
        "재귀",
    )
    print("\n[KO] 재귀에서 막힘")
    print("  first:", first)
    print("  path :", " → ".join(path))
    assert first == "변수", first

    # Curated quizzes exist with valid keys (EN + KO + alias)
    for name in ["Recursion", "재귀", "for loop", "반복문"]:
        qs = BB.questions_for(name)
        assert qs and all(0 <= q["answer_index"] < len(q["choices"]) for q in qs), name
        print(f"\n  quiz {name!r}: {qs[0]['stem']} → {qs[0]['choices'][qs[0]['answer_index']]}")

    print("\n" + "=" * 74)
    print("✅ Coding curriculum works like math/science: reliable DAG, back-tracking,")
    print("   and trusted auto-graded quizzes — English and Korean.")
    print("=" * 74)


if __name__ == "__main__":
    main()
