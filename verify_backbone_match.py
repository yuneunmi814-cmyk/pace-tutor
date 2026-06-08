"""백본 매칭/커버리지 검증 — 결정적(LLM·임베딩 불필요).

배경(이 턴의 두 음성 결과):
  - 로컬 LLM(llama3.1:8b) 선수관계 추출 F1 ~0.33 (eval_extraction.py)
  - 로컬 임베딩(nomic-embed-text) 한국어 개념 매칭 변별력 없음 (실측)
→ 매칭은 '또 다른 약한 모델'이 아니라 결정적 방법으로: 정확/별칭(권위) + 보수적 퍼지(보조).

이 스크립트가 보증하는 것:
  1) 정확/별칭/띄어쓰기 매칭은 안정적
  2) 보수적 퍼지는 긴 변형('증발현상'→'증발')은 잡고 무관어('미분')는 거부 (오탐 없음)
  3) 짧은 한 글자 STT 오류('은결')는 퍼지로 못 잡음 → 별칭 필요(한계 명시)
  4) coverage() 가 백본 확충용 matched/novel 리포트를 정확히 산출
"""

from ingest.backbone import Backbone

BB = Backbone.from_json("data/backbone_seed.json")


def main():
    print("=" * 74)
    print("백본 매칭 — 정확/별칭(권위) + 보수적 퍼지(보조)")
    print("=" * 74)

    # 1) 정확/별칭/띄어쓰기 (fuzzy 불필요)
    assert BB.match("최대공약수") == "gcd"
    assert BB.match("최대 공약수") == "gcd"          # 별칭
    assert BB.match("인수 분해") == "factoring"       # 띄어쓰기(_norm)
    assert BB.match("은결") == "condensation"         # 별칭(STT 오류 등록됨)
    print("  ✅ 정확/별칭/띄어쓰기 매칭 안정")

    # 2) 보수적 퍼지: 긴 변형은 잡고, 무관어는 거부
    assert BB.match("증발현상", fuzzy=True) == "evaporation"   # 0.67 ≥ 임계
    assert BB.match("물순환", fuzzy=True) == "water_cycle"      # 0.86
    assert BB.match("미분", fuzzy=True) is None                 # 약분/통분과 0.50 충돌 → 거부
    assert BB.match("피타고라스", fuzzy=True) is None           # 무관 → 거부
    print("  ✅ 퍼지: 긴 변형 매칭 + 무관어 거부 (오탐 없음)")

    # 3) 한계 명시 — 짧은 한 글자 오류는 퍼지로 못 잡음 (별칭 없으면 None)
    #    '은절'(가상의 미등록 STT 오류)은 퍼지로도 안전하게 매칭 불가
    assert BB.match("은절", fuzzy=True) is None
    print("  ✅ 한계 확인: 짧은 한 글자 오류는 별칭으로만 커버 가능 (퍼지는 안전하게 거부)")

    # 4) 커버리지 리포트 (백본 확충 워크플로우)
    extracted = ["최대공약수", "약분", "이차방정식", "행렬", "미적분", "증발현상"]
    cov = BB.coverage(extracted, fuzzy=True)
    print("\n— coverage() 리포트 —")
    print(f"  커버리지율: {cov['rate']*100:.0f}%")
    print(f"  매칭됨: {[f'{a}→{b}' for a,b in cov['matched']]}")
    print(f"  신규(백본에 추가 필요): {cov['novel']}")
    assert "행렬" in cov["novel"] and "미적분" in cov["novel"]
    assert any(a == "증발현상" for a, _ in cov["matched"])
    print("  ✅ 커버리지 리포트 정확 (신규 개념 식별 → 백본 확충 가이드)")

    print("\n" + "=" * 74)
    print("결론: 매칭은 결정적으로 안전. 퍼지는 별칭 유지 부담을 '긴 변형'에서만 덜어준다.")
    print("      짧은 개념의 한 글자 오류는 큐레이션 별칭이 답(로컬모델 대체 불가).")
    print("=" * 74)


if __name__ == "__main__":
    main()
