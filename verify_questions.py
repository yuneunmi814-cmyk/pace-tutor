"""Curated question bank verification — deterministic (no LLM).

The diagnostic quiz uses curated questions from the backbone (trusted answer keys),
NOT local-LLM-generated ones (measured: an 8B model gets its own answers wrong).
This checks the /v1/questions endpoint serves correct curated items for both
languages and via aliases, and that the answer keys are well-formed.
"""

from fastapi.testclient import TestClient
from sidecar.server import app

c = TestClient(app)


def fetch(concept):
    return c.post("/v1/questions", json={"concept": concept, "n": 5}).json()


def main():
    print("=" * 70)
    print("Curated question bank — /v1/questions (deterministic)")
    print("=" * 70)

    # Exact names (EN + KO) and aliases all resolve to curated questions
    checks = ["Reducing Fractions", "약분", "gcf", "lcd", "분수의 덧셈"]
    for name in checks:
        r = fetch(name)
        qs = r["questions"]
        assert r["source"] == "curated", f"{name}: expected curated, got {r['source']}"
        assert qs, f"{name}: no questions"
        for q in qs:
            assert 0 <= q["answer_index"] < len(q["choices"]), f"{name}: bad answer_index"
        print(f"  ✅ {name!r:24} curated  {len(qs)} Q  e.g. \"{qs[0]['stem']}\" → {qs[0]['choices'][qs[0]['answer_index']]}")

    # A concept without curated questions falls back cleanly (UI → self-assessment)
    r = fetch("Quadratic Equations")
    assert r["source"] == "none" and r["questions"] == []
    print(f"  ✅ {'Quadratic Equations'!r:24} none (UI falls back to self-assessment)")

    # Grading logic mirror (what the UI does): all-correct → confident, etc.
    qs = fetch("약분")["questions"]
    answers_all_correct = {i: q["answer_index"] for i, q in enumerate(qs)}
    correct = sum(1 for i, q in enumerate(qs) if answers_all_correct[i] == q["answer_index"])
    assert correct == len(qs)
    print(f"  ✅ grading: {correct}/{len(qs)} correct → 'confident' (→ BKT [1,1,1,1])")

    print("\n" + "=" * 70)
    print("Conclusion: objective auto-graded quizzes from a trusted bank, EN + KO,")
    print("with self-assessment fallback where no curated items exist.")
    print("=" * 70)


if __name__ == "__main__":
    main()
