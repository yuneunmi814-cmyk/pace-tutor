"""입력 로더 — 영상/오디오/PDF/텍스트/자막을 모두 '텍스트'로 환원.

핵심: 파이프라인 하류(transcript_to_graph)는 입력 종류를 모른다("텍스트→그래프").
따라서 입력별 '앞단'만 텍스트를 뽑아주면 동일 플로우로 합류한다.

지원:
  - 텍스트:  .txt .md
  - 자막:    .srt .vtt   (타임스탬프/인덱스 제거 후 본문만)
  - PDF:     .pdf        (디지털 PDF, pypdf). ⚠️ 스캔 PDF는 OCR 별도 필요
  - 미디어:  .mp4 .mov .mkv .webm .mp3 .wav .m4a .aac .flac (faster-whisper, 영상=오디오 동일)
"""

from __future__ import annotations

import re
from pathlib import Path

from engine import ConceptGraph
from .pipeline import transcript_to_graph

TEXT_EXT = {".txt", ".md"}
SUBTITLE_EXT = {".srt", ".vtt"}
PDF_EXT = {".pdf"}
MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".aiff"}


def _strip_subtitles(raw: str) -> str:
    """SRT/VTT 에서 본문만 추출 (인덱스·타임코드·WEBVTT 헤더 제거)."""
    out = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s == "WEBVTT":
            continue
        if s.isdigit():                                  # SRT 인덱스
            continue
        if "-->" in s:                                   # 타임코드 라인
            continue
        out.append(s)
    return " ".join(out)


def load_text(path: str, stt_model_size: str = "small",
              language: str | None = None, initial_prompt: str | None = None) -> str:
    """어떤 입력이든 → 전사 텍스트."""
    ext = Path(path).suffix.lower()

    if ext in TEXT_EXT:
        return Path(path).read_text(encoding="utf-8")

    if ext in SUBTITLE_EXT:
        return _strip_subtitles(Path(path).read_text(encoding="utf-8"))

    if ext in PDF_EXT:
        from pypdf import PdfReader  # 지연 import
        reader = PdfReader(path)
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        if not text.strip():
            raise ValueError(
                "PDF 에서 텍스트를 못 뽑음 — 스캔본일 수 있음(OCR 필요)."
            )
        return text

    if ext in MEDIA_EXT:
        from .stt import transcribe  # 지연 import (faster-whisper)
        text, _segs = transcribe(path, model_size=stt_model_size,
                                 language=language, initial_prompt=initial_prompt)
        return text

    raise ValueError(f"지원하지 않는 확장자: {ext}")


def source_to_graph(path: str, model: str = "llama3.1:8b", backbone=None,
                    stt_model_size: str = "small", language: str | None = None,
                    initial_prompt: str | None = None) -> ConceptGraph:
    """파일(영상/오디오/PDF/텍스트/자막) → ConceptGraph (통합 진입점)."""
    text = load_text(path, stt_model_size=stt_model_size,
                     language=language, initial_prompt=initial_prompt)
    return transcript_to_graph(text, model=model, backbone=backbone)
