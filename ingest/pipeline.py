"""end-to-end 오케스트레이션.

  transcript_to_graph(text)  : 자막 텍스트 → engine.ConceptGraph  (STT 불필요)
  video_to_graph(path)       : 영상 파일 → engine.ConceptGraph    (faster-whisper 필요)

생성된 ConceptGraph 는 그대로 engine.Recommender 에 투입된다.

선수관계 '구조'는 자료 자체에서 뽑는다(structure 인자):
  - "llm-order"(기본): LLM에 기초→고급 정렬을 시켜 사슬화. eval_structure.py 측정 순서정확도 1.00.
                        (같은 모델의 '관계 추출'은 0.5 수준이라 정렬 방식이 훨씬 신뢰됨)
  - "transcript": 자막 첫 등장 순서(결정적, 단 제목이 앞에 나오면 약함)
  - "llm-edges":  (구) LLM 관계 추출
backbone 은 '선택적 오버레이' — 자료에 없는 기초 끌어오기 + 병렬 구조 보정에만 쓴다.
"""

from __future__ import annotations

from engine import ConceptGraph

from .chunk import chunk_text
from .extract import extract_concepts, extract_prereqs, DEFAULT_MODEL
from .graph_build import build_graph
from .structure import order_by_transcript, order_by_llm, chain_edges


def _concepts_from_text(text: str, model: str, chunk_size: int, overlap: int) -> list[str]:
    concepts: list[str] = []
    seen: set[str] = set()
    for ch in chunk_text(text, chunk_size=chunk_size, overlap=overlap):
        for c in extract_concepts(ch, model=model):
            if c.lower() not in seen:
                seen.add(c.lower())
                concepts.append(c)
    return concepts


def transcript_to_graph(text: str, model: str = DEFAULT_MODEL,
                        chunk_size: int = 400, overlap: int = 50,
                        structure: str = "llm-order", backbone=None,
                        pull_prereqs: bool = True) -> ConceptGraph:
    """자막 → ConceptGraph. 개념은 자료에서 추출, 구조는 structure 방식으로 자료에서 도출.

    backbone 이 있으면 자료에 없는 하위 선수개념까지 끌어온다(pull_prereqs).
    """
    concepts = _concepts_from_text(text, model, chunk_size, overlap)

    if structure == "transcript":
        edges = chain_edges(order_by_transcript(concepts, text))
    elif structure == "llm-edges":
        edges = [(e.prerequisite, e.concept) for e in extract_prereqs(concepts, model=model)]
    else:  # "llm-order" (기본, 측정상 가장 신뢰)
        edges = chain_edges(order_by_llm(concepts, model=model))

    if backbone is not None:
        names, edge_pairs = backbone.augment(concepts, edges, fuzzy=True,
                                             pull_prereqs=pull_prereqs)
        return build_graph(names, edge_pairs)
    return build_graph(concepts, edges)


def video_to_graph(video_path: str, model: str = DEFAULT_MODEL,
                   stt_model_size: str = "base", language: str | None = None,
                   initial_prompt: str | None = None,
                   structure: str = "llm-order", backbone=None,
                   pull_prereqs: bool = True) -> ConceptGraph:
    from .stt import transcribe  # 지연 import (faster-whisper 의존)

    text, _segments = transcribe(video_path, model_size=stt_model_size,
                                 language=language, initial_prompt=initial_prompt)
    return transcript_to_graph(text, model=model, structure=structure,
                               backbone=backbone, pull_prereqs=pull_prereqs)
