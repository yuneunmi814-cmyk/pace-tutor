"""선수관계 추출 품질 평가 — 기존(one-shot) vs 개선(페어와이즈).

개념 이름 변동을 제거하기 위해 **개념 목록을 고정**하고, 골드 선수관계 엣지 대비
precision/recall/F1 을 측정한다(엣지 추출 정확도만 비교). Ollama 필요.

실행: .venv/bin/python eval_extraction.py
"""

from collections import defaultdict

from ingest.extract import extract_prereqs, extract_prereqs_pairwise

MODEL = "llama3.1:8b"
TRIALS = 3

# 고정 개념 목록 (수학 분수·대수 사슬 — 선수관계가 명확)
CONCEPTS = ["최대공약수", "약분", "통분", "분수의 덧셈", "일차방정식", "이차방정식", "인수분해"]

# 골드 선수관계 (prereq → concept), 정규화 비교용 소문자 튜플
GOLD = {
    ("최대공약수", "약분"),
    ("최대공약수", "통분"),
    ("약분", "분수의 덧셈"),
    ("통분", "분수의 덧셈"),
    ("분수의 덧셈", "일차방정식"),
    ("일차방정식", "이차방정식"),
    ("인수분해", "이차방정식"),
}


def _norm(edges):
    return {(e.prerequisite.strip(), e.concept.strip()) for e in edges}


def _prf(pred: set, gold: set):
    tp = len(pred & gold)
    prec = tp / len(pred) if pred else 0.0
    rec = tp / len(gold) if gold else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return prec, rec, f1


def run(name, fn):
    print(f"\n── {name} ({TRIALS}회 평균) ──")
    agg = defaultdict(float)
    edge_freq = defaultdict(int)
    for t in range(TRIALS):
        pred = _norm(fn())
        p, r, f = _prf(pred, GOLD)
        agg["p"] += p; agg["r"] += r; agg["f"] += f; agg["n"] += len(pred)
        for e in pred:
            edge_freq[e] += 1
        print(f"   trial {t+1}: P={p:.2f} R={r:.2f} F1={f:.2f}  (엣지 {len(pred)}개)")
    print(f"   평균:   P={agg['p']/TRIALS:.2f} R={agg['r']/TRIALS:.2f} "
          f"F1={agg['f']/TRIALS:.2f}  (평균 엣지 {agg['n']/TRIALS:.1f}개)")
    # 안정적으로 잡은 골드 엣지 / 놓친 골드 엣지
    stable = {e for e, c in edge_freq.items() if c == TRIALS and e in GOLD}
    missed = GOLD - set(edge_freq)
    print(f"   매번 맞춘 골드: {sorted(a+'→'+b for a,b in stable)}")
    print(f"   한 번도 못잡은 골드: {sorted(a+'→'+b for a,b in missed)}")
    return agg["f"] / TRIALS


def main():
    print("=" * 74)
    print("선수관계 추출 품질: 기존(one-shot) vs 개선(페어와이즈)")
    print(f"고정 개념 {len(CONCEPTS)}개, 골드 엣지 {len(GOLD)}개, 모델 {MODEL}")
    print("=" * 74)

    f_base = run("기존: one-shot (전체 엣지 한 번에)",
                 lambda: extract_prereqs(CONCEPTS, model=MODEL))
    f_pair = run("개선: 페어와이즈 (개념별 질의)",
                 lambda: extract_prereqs_pairwise(CONCEPTS, model=MODEL, samples=1))
    f_pair3 = run("개선+: 페어와이즈 3샘플 다수결",
                  lambda: extract_prereqs_pairwise(CONCEPTS, model=MODEL, samples=3))

    print("\n" + "=" * 74)
    print(f"F1 요약 — one-shot {f_base:.2f}  →  페어와이즈 {f_pair:.2f}  "
          f"→  페어와이즈3 {f_pair3:.2f}")
    best = max(f_base, f_pair, f_pair3)
    print(f"최고: {best:.2f}  ({'페어와이즈 계열' if best in (f_pair, f_pair3) else 'one-shot'})")
    print("=" * 74)


if __name__ == "__main__":
    main()
