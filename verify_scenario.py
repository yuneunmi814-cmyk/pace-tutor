"""검증 시나리오 (청사진 §9):
중3 학생이 '이차방정식'에서 막힘 → 진단 → 추천이 '분수/약분/등식' 같은
*기초*로 내려가는지, 그리고 기초를 통달하면 위로 올라가는지 확인한다.

통과 기준:
  1) 아무것도 모르는 상태에서 추천 1순위가 '이차방정식'이 아니라 뿌리 기초여야 함
  2) 기초를 통달시키면 추천이 점점 상위 개념으로 '진도'를 올려야 함
  3) 선수개념이 안 끝났는데 상위 개념이 먼저 추천되면 안 됨 (P 페널티 동작)
"""

from engine import ConceptGraph, Concept, LearnerState, Recommender


def build_math_graph() -> ConceptGraph:
    # 초등 산수 → 중등 대수로 이어지는 작은 수학 선수개념 사슬
    return ConceptGraph([
        Concept("gcd", "최대공약수", prereqs=[], difficulty=0.1, grade="초5"),
        Concept("reduce_fraction", "약분", prereqs=["gcd"], difficulty=0.2, grade="초5"),
        Concept("fraction_add", "분수의 덧셈", prereqs=["reduce_fraction"], difficulty=0.3, grade="초5"),
        Concept("equation_basics", "등식의 성질", prereqs=[], difficulty=0.3, grade="중1"),
        Concept("linear_equation", "일차방정식", prereqs=["equation_basics", "fraction_add"], difficulty=0.5, grade="중1"),
        Concept("multiply_poly", "다항식의 곱셈", prereqs=["linear_equation"], difficulty=0.6, grade="중2"),
        Concept("factoring", "인수분해", prereqs=["multiply_poly"], difficulty=0.7, grade="중3"),
        Concept("quadratic_equation", "이차방정식", prereqs=["factoring", "linear_equation"], difficulty=0.9, grade="중3"),
    ])


def show_top(rec, learner, k=3):
    rows = rec.rank(learner)[:k]
    for i, r in enumerate(rows, 1):
        print(f"   {i}. {r.name:<10} (개념:{r.concept_id:<18} "
              f"숙달 {r.mastery*100:4.1f}%  점수 {r.score:+7.3f}  "
              f"준비도P {r.readiness:+6.3f}  보충R {r.remediation:+6.3f})")
    return rows[0]


def main():
    graph = build_math_graph()
    learner = LearnerState(graph)
    # r_star=0 (선수개념 엄격), W_p=2.0 (readiness 강하게) — 어린/기초부족 학습자 설정
    rec = Recommender(graph, r_star=0.0, W_p=2.0)

    print("=" * 78)
    print("시나리오: 중3 학생, '이차방정식' 단원에서 막혀 도움을 요청")
    print("=" * 78)

    # 1) 학생이 이차방정식 진단 문항을 풀어봄 → 다 틀림
    print("\n[1] 이차방정식 진단 문항 3개 → 전부 오답")
    learner.update_many("quadratic_equation", [0, 0, 0])
    print("    이차방정식 숙달확률: {:.1f}%".format(learner.mastery_of("quadratic_equation") * 100))

    print("\n[2] 엔진이 추천하는 '다음 학습' (전체 개념 사전확률 상태):")
    first = show_top(rec, learner, k=4)
    assert first.concept_id != "quadratic_equation", \
        "❌ 실패: 기초가 없는데 이차방정식을 추천함"
    assert not first.concept_id in ("factoring", "multiply_poly", "quadratic_equation"), \
        "❌ 실패: 선수개념 미완인데 상위 개념을 추천함 (P 페널티 미작동?)"
    print(f"\n    ✅ 1순위 = '{first.name}' — 막힌 단원이 아니라 뿌리 기초로 역추적됨")

    # 3) 자기 속도로 기초부터 차근차근 통달해 나가는 과정 시뮬레이션
    print("\n[3] 학생이 추천을 따라 '자기 속도로' 기초부터 통달해 나감:")
    progression = []
    for step in range(1, 9):
        nxt = rec.next_concept(learner)
        progression.append(nxt.name)
        print(f"\n  - {step}단계 추천: 「{nxt.name}」 (현재 숙달 {nxt.mastery*100:.1f}%)")
        # 학생이 그 개념을 연습해 통달 (정답 반복)
        p = learner.update_many(nxt.concept_id, [1, 1, 1, 1, 1, 1])
        print(f"      → 연습 후 「{nxt.name}」 숙달 {p*100:.1f}%  "
              f"(통달? {rec.is_mastered(learner, nxt.concept_id)})")
        if rec.is_mastered(learner, "quadratic_equation"):
            print("\n  🎉 최종 목표 '이차방정식'까지 통달 도달!")
            break

    print("\n[4] 학습 경로(추천 순서):")
    print("    " + " → ".join(progression))

    # 통과 기준 검증: 이차방정식이 경로의 맨 마지막에 등장해야 함
    assert "이차방정식" in progression, "❌ 실패: 최종 목표에 도달하지 못함"
    assert progression.index("이차방정식") == len(progression) - 1, \
        "❌ 실패: 이차방정식이 기초보다 먼저 추천됨"
    # 첫 추천은 선수개념 없는 뿌리(gcd 또는 equation_basics) 중 하나
    assert progression[0] in ("최대공약수", "등식의 성질"), \
        f"❌ 실패: 첫 추천이 뿌리 기초가 아님 ({progression[0]})"

    print("\n" + "=" * 78)
    print("✅ 모든 통과 기준 충족:")
    print("   1) 막힌 단원이 아니라 뿌리 기초부터 추천  ")
    print("   2) 선수개념 미완 상위 개념은 P 페널티로 후순위  ")
    print("   3) 자기 속도로 기초→상위로 진도가 자연히 상승해 최종 목표 도달")
    print("=" * 78)


if __name__ == "__main__":
    main()
