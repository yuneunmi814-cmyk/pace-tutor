"""영상 → 개념 그래프 자동 생성 파이프라인.

설계 근거: video-to-conceptgraph-reference.md
  STT(stt) → 청킹(chunk) → 2단계 추출(extract) → DAG화/난이도(graph_build)
  → (선택) 진단문항(questions) → 오케스트레이션(pipeline)

LLM(Ollama)·STT(faster-whisper)에 의존하지 않는 순수 모듈(chunk, graph_build)은
단독 import 가능하다. extract/stt/questions 는 사용 시점에 해당 의존성을 import 한다.
"""

from .chunk import chunk_text
from .graph_build import build_graph, break_cycles, assign_difficulty, normalize_key
from .loaders import load_text, source_to_graph

__all__ = [
    "chunk_text",
    "build_graph",
    "break_cycles",
    "assign_difficulty",
    "normalize_key",
    "load_text",
    "source_to_graph",
]
