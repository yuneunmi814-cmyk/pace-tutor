"""교과목 무관성 + 수준대 페이스메이킹 데모.

증명하려는 것:
  (A) 엔진은 교과목과 무관하다 — 수학이 아닌 '프로그래밍', '영어 문법'에도
      코드 한 줄 안 바꾸고 동일하게 동작한다. 바뀌는 건 ConceptGraph 내용뿐.
  (B) 같은 그래프라도 수준대(초등/중고등/대학·성인)에 따라 역추적 '바닥'이
      달라져, 같은 막힘이라도 페이스가 달라진다.
"""

from engine import (
    ConceptGraph, Concept, LearnerState, Recommender,
    ELEMENTARY, TERTIARY_ADULT,
)


def programming_graph() -> ConceptGraph:
    return ConceptGraph([
        Concept("variable", "변수", prereqs=[], difficulty=0.1),
        Concept("conditional", "조건문", prereqs=["variable"], difficulty=0.2),
        Concept("loop", "반복문", prereqs=["conditional"], difficulty=0.3),
        Concept("function", "함수", prereqs=["variable"], difficulty=0.4),
        Concept("call_stack", "호출 스택", prereqs=["function"], difficulty=0.6),
        Concept("recursion", "재귀", prereqs=["function", "call_stack"], difficulty=0.7),
        Concept("divide_conquer", "분할정복", prereqs=["recursion", "loop"], difficulty=0.85),
    ])


def english_grammar_graph() -> ConceptGraph:
    return ConceptGraph([
        Concept("noun", "명사", prereqs=[], difficulty=0.1),
        Concept("verb", "동사", prereqs=[], difficulty=0.1),
        Concept("sentence", "문장 기본구조", prereqs=["noun", "verb"], difficulty=0.25),
        Concept("pronoun", "대명사", prereqs=["noun"], difficulty=0.3),
        Concept("clause", "절(clause)", prereqs=["sentence"], difficulty=0.5),
        Concept("relative_pronoun", "관계대명사", prereqs=["clause", "pronoun"], difficulty=0.7),
    ])


def run(subject, graph, stuck_at, stuck_name):
    print("\n" + "=" * 78)
    print(f"교과목: {subject}   (학습자가 '{stuck_name}'에서 막힘)")
    print("=" * 78)

    for band in (ELEMENTARY, TERTIARY_ADULT):
        learner = LearnerState(graph)
        floor = learner.apply_level_floor(band)          # 수준대 바닥 적용
        learner.update_many(stuck_at, [0, 0, 0])         # 막힌 개념 진단 → 오답
        rec = Recommender(graph, r_star=0.0, W_p=2.0)

        # 자기 속도 학습 경로 시뮬레이션
        path = []
        for _ in range(graph.n + 2):
            nxt = rec.next_concept(learner)
            if rec.is_mastered(learner, stuck_at):
                break
            path.append(nxt.name)
            learner.update_many(nxt.concept_id, [1, 1, 1, 1, 1, 1])
            if nxt.concept_id == stuck_at:
                break

        floor_names = [c.name for c in graph.concepts if c.id in floor] or ["(없음)"]
        print(f"\n  ▶ {band.label}")
        print(f"     이미 안다고 가정(바닥): {', '.join(floor_names)}")
        print(f"     첫 추천: 「{path[0]}」")
        print(f"     학습 경로: {' → '.join(path)}")


def main():
    run("프로그래밍 (재귀)", programming_graph(), "divide_conquer", "분할정복")
    run("영어 문법 (관계대명사)", english_grammar_graph(), "relative_pronoun", "관계대명사")

    print("\n" + "=" * 78)
    print("결론:")
    print("  • 엔진 코드는 한 줄도 안 바뀜 — 교과목은 ConceptGraph 데이터일 뿐 (무관)")
    print("  • 초등학생은 뿌리 기초까지 역추적, 대학·성인은 기초를 건너뛰고 더 위에서 시작")
    print("  • → 같은 막힘도 수준대에 맞춰 '자기 속도'로 페이스메이킹됨")
    print("=" * 78)


if __name__ == "__main__":
    main()
