"""end-to-end 오케스트레이션.

  transcript_to_graph(text)  : 자막 텍스트 → engine.ConceptGraph  (STT 불필요)
  video_to_graph(path)       : 영상 파일 → engine.ConceptGraph    (faster-whisper 필요)

생성된 ConceptGraph 는 그대로 engine.Recommender 에 투입된다.
"""

from __future__ import annotations

from engine import ConceptGraph

from .chunk import chunk_text
from .extract import extract_all, DEFAULT_MODEL
from .graph_build import build_graph


def transcript_to_graph(text: str, model: str = DEFAULT_MODEL,
                        chunk_size: int = 400, overlap: int = 50,
                        pairwise: bool = False, samples: int = 1,
                        backbone=None) -> ConceptGraph:
    """자막 → ConceptGraph.

    LLM 선수관계 추출은 약한 prior 다(eval_extraction.py 측정: 8B 모델 F1 ~0.33).
    `backbone`(교육과정 백본 사전)을 주면 추출된 개념을 표준 개념에 매핑하고
    검증된 선수관계를 주입해 신뢰도를 끌어올린다(backbone 우선).
    """
    chunks = chunk_text(text, chunk_size=chunk_size, overlap=overlap)
    concepts, edges = extract_all(chunks, model=model, pairwise=pairwise, samples=samples)
    if backbone is not None:
        concepts, edge_pairs = backbone.augment(concepts, edges)
        return build_graph(concepts, edge_pairs)
    return build_graph(concepts, edges)


def video_to_graph(video_path: str, model: str = DEFAULT_MODEL,
                   stt_model_size: str = "base", language: str | None = None,
                   initial_prompt: str | None = None, backbone=None) -> ConceptGraph:
    from .stt import transcribe  # 지연 import (faster-whisper 의존)

    text, _segments = transcribe(video_path, model_size=stt_model_size,
                                 language=language, initial_prompt=initial_prompt)
    return transcript_to_graph(text, model=model, backbone=backbone)
