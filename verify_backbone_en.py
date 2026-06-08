"""English curriculum backbone verification — deterministic (no LLM).

Mirrors verify_backbone.py for the Korean seed: even with noisy concept names
and zero/garbage LLM edges, the English backbone aligns concepts to canonical
forms and injects verified prerequisites to produce a correct DAG and path.
"""

from engine import LearnerState, Recommender
from ingest.backbone import Backbone
from ingest.graph_build import build_graph

BB = Backbone.from_jsons(["data/backbone_en.json", "data/backbone_seed.json"])


def case(title, noisy_concepts, llm_edges, target_name, expect_first):
    print("=" * 74)
    print(title)
    print("=" * 74)
    print(f"  input concepts (noisy): {noisy_concepts}")
    print(f"  LLM edges (sparse/wrong): {llm_edges or '(none)'}")
    names, edges = BB.augment(noisy_concepts, llm_edges, fuzzy=True)
    g = build_graph(names, edges)
    print(f"\n  after backbone alignment — {g.n} concepts:")
    for c in g.concepts:
        pr = [g.concepts[g.index(p)].name for p in c.prereqs]
        print(f"    {c.name:<26} diff {c.difficulty}  prereqs={pr}")
    target = next(c.id for c in g.concepts if c.name == target_name)
    learner = LearnerState(g); learner.update_many(target, [0, 0, 0])
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    nxt = rec.next_concept(learner)
    path = []
    for _ in range(g.n + 1):
        n = rec.next_concept(learner); path.append(n.name)
        if rec.is_mastered(learner, target): break
        learner.update_many(n.concept_id, [1, 1, 1, 1, 1, 1])
        if n.concept_id == target: break
    print(f"\n  stuck on '{target_name}' → first: {nxt.name}")
    print(f"  path: {' → '.join(path)}")
    assert nxt.name == expect_first, f"expected {expect_first}, got {nxt.name}"
    print(f"  ✅ pass (first = {expect_first})\n")


def main():
    # Science: aliases ("GCF"-style) + zero LLM edges
    case(
        "[Science] Water cycle — aliases + zero LLM edges, still a full DAG",
        noisy_concepts=["the water cycle", "evaporate", "condensing", "clouds", "rainfall", "states of water"],
        llm_edges=[],
        target_name="Water Cycle", expect_first="States of Matter",
    )
    # Math: aliases + a wrong reverse LLM edge that the backbone overrides
    case(
        "[Math] Fractions/algebra — wrong LLM edge overridden by backbone",
        noisy_concepts=["quadratics", "factoring polynomials", "multiplying polynomials", "linear equation", "fraction addition", "simplifying fractions", "lcd", "gcf"],
        llm_edges=[("Quadratic Equations", "Greatest Common Divisor")],
        target_name="Quadratic Equations", expect_first="Greatest Common Divisor",
    )
    print("=" * 74)
    print("Conclusion: English content now gets the same deterministic, reliable")
    print("learning path as Korean — the LLM only needs to surface concept names.")
    print("=" * 74)


if __name__ == "__main__":
    main()
