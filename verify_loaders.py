"""입력 로더 검증 — 텍스트/자막/PDF 가 모두 '텍스트'로 환원되는지(결정적, LLM 불필요).

오디오/영상은 STT 로 이미 검증됨(verify 음성 테스트). 여기서는 나머지 입력형식이
동일 플로우의 앞단(load_text)을 통과하는지 확인한다.
"""

import os
import tempfile

from ingest.loaders import load_text

WC = ("오늘은 물의 순환에 대해 배웁니다. 물은 고체, 액체, 기체로 존재합니다. "
      "증발과 응결을 거쳐 구름이 되고 강수로 떨어집니다.")


def main():
    d = tempfile.mkdtemp(prefix="pt_loaders_")
    print("=" * 70)
    print("입력 로더 검증 (텍스트/자막/PDF → 텍스트)")
    print("=" * 70)

    # 1) 텍스트 파일
    txt = os.path.join(d, "lecture.txt")
    with open(txt, "w", encoding="utf-8") as f:
        f.write(WC)
    t1 = load_text(txt)
    assert "증발" in t1 and "응결" in t1
    print(f"  ✅ .txt  → {len(t1)}자, 본문 보존")

    # 2) 자막(SRT) — 타임코드/인덱스 제거
    srt = os.path.join(d, "lecture.srt")
    with open(srt, "w", encoding="utf-8") as f:
        f.write("1\n00:00:01,000 --> 00:00:04,000\n물은 고체 액체 기체로 존재합니다.\n\n"
                "2\n00:00:04,000 --> 00:00:07,000\n증발과 응결을 거쳐 구름이 됩니다.\n")
    t2 = load_text(srt)
    assert "-->" not in t2 and "증발" in t2 and "00:00" not in t2
    print(f"  ✅ .srt  → 타임코드 제거됨, 본문만: \"{t2[:30]}…\"")

    # 3) PDF (디지털, 한국어 CID 폰트로 생성 → pypdf 추출)
    pdf = os.path.join(d, "lecture.pdf")
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
    c = canvas.Canvas(pdf)
    c.setFont("HYSMyeongJo-Medium", 14)
    y = 800
    for line in ["물의 순환 강의", "증발은 액체가 기체로 변하는 것이다.",
                 "응결을 거쳐 구름이 되고 강수로 떨어진다."]:
        c.drawString(60, y, line); y -= 30
    c.save()
    t3 = load_text(pdf)
    assert "증발" in t3 and "응결" in t3
    print(f"  ✅ .pdf  → 디지털 PDF 텍스트 추출 성공: \"{t3.strip()[:30]}…\"")

    print("\n  (오디오/영상은 STT 로 이미 검증됨 — 동일 load_text 경유)")
    print("=" * 70)
    print("결론: 영상·오디오·PDF·텍스트·자막 모두 load_text 로 텍스트가 되어")
    print("      기존 transcript_to_graph(텍스트→그래프) 동일 플로우로 합류한다.")
    print("=" * 70)


if __name__ == "__main__":
    main()
