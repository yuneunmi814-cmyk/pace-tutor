"""자막 청킹 — ai-knowledge-graph text_utils.chunk_text 차용 (단어수 기준 overlap).

강의 자막은 한 청크에 한 주제가 담기도록 300~500단어 + overlap 50 권장
(청사진 §5-3: 너무 작으면 선수관계 문맥 끊김, 너무 크면 작은 로컬모델이 개념 놓침).
"""

from __future__ import annotations


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text] if text.strip() else []
    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks
