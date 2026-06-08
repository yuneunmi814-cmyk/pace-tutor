"""pace-tutor 사이드카 서버 — engine + ingest 를 HTTP API 로 노출.

골격 출처: dieharders/example-tauri-v2-python-server-sidecar src/backends/main.py
  - FastAPI on 127.0.0.1:8008 (외부 노출 차단)
  - stdin "sidecar shutdown" → SIGINT 자결 (PyInstaller 부트로더 PID 함정 회피)

엔드포인트:
  GET  /v1/connect            헬스체크
  GET  /v1/bands              수준대 목록
  POST /v1/ingest             자막/영상/직접개념 → 개념 그래프 생성 (graph_id 반환)
  GET  /v1/graph/{graph_id}   생성된 그래프 조회
  POST /v1/recommend          진단 응답(+수준대) → 다음 학습 개념 + 랭킹
  POST /v1/path               목표 개념까지 자기속도 학습 경로 시뮬레이션
  POST /v1/questions          개념별 진단 문항 생성 (Ollama 필요)
"""

from __future__ import annotations

import os
import signal
import sys
import asyncio
import threading
import uuid

from fastapi import FastAPI, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from engine import (
    Concept, ConceptGraph, LearnerState, Recommender, BANDS,
)
from ingest.graph_build import build_graph

PORT_API = 8008

# 교육과정 백본(있으면 로드) — LLM 추출 신뢰도 보정용. 없으면 None.
# PyInstaller 번들에서도 찾도록 여러 후보 경로 탐색(_MEIPASS 포함, 번들 함정 회피).
_BACKBONE = None
try:
    import os as _os
    import sys as _sys
    from ingest.backbone import Backbone
    # 언어별 백본을 모두 병합 로드 (영어 + 한국어). 후보 디렉터리 탐색(_MEIPASS 포함).
    _files = ["backbone_en.json", "backbone_seed.json"]
    _dirs = [
        _os.path.join(_os.path.dirname(__file__), "..", "data"),
        _os.path.join(getattr(_sys, "_MEIPASS", ""), "data"),
        _os.path.join(_os.getcwd(), "data"),
    ]
    for _d in _dirs:
        _paths = [_os.path.join(_d, f) for f in _files if _os.path.exists(_os.path.join(_d, f))]
        if _paths:
            _BACKBONE = Backbone.from_jsons(_paths)
            break
except Exception:
    _BACKBONE = None

app = FastAPI(title="pace-tutor sidecar", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # 개발용. 배포 시 tauri 오리진으로 제한
    allow_methods=["*"],
    allow_headers=["*"],
)

# 메모리 그래프 저장소 (운영은 SQLite). graph_id → ConceptGraph
GRAPHS: dict[str, ConceptGraph] = {}


def _graph_payload(g: ConceptGraph) -> list[dict]:
    return [
        {"id": c.id, "name": c.name, "prereqs": c.prereqs,
         "difficulty": c.difficulty, "grade": c.grade}
        for c in g.concepts
    ]


def _get_graph(graph_id: str) -> ConceptGraph:
    g = GRAPHS.get(graph_id)
    if g is None:
        raise HTTPException(404, f"unknown graph_id: {graph_id}")
    return g


def _build_learner(g: ConceptGraph, band_key: str | None, responses: dict) -> LearnerState:
    learner = LearnerState(g)
    if band_key and band_key in BANDS:
        learner.apply_level_floor(BANDS[band_key])   # 수준대 바닥 가정
    for cid, resp in (responses or {}).items():
        if cid in g.ids:
            learner.update_many(cid, resp)            # 진단 퀴즈 반영(가정 덮어씀)
    return learner


# ── 엔드포인트 ───────────────────────────────────────────────────────────────
@app.get("/v1/connect")
def connect():
    return {"status": "ok", "port": PORT_API, "pid": os.getpid(),
            "graphs": list(GRAPHS.keys())}


@app.get("/v1/bands")
def bands():
    return {"bands": [{"key": b.key, "label": b.label} for b in BANDS.values()]}


@app.post("/v1/ingest")
def ingest(payload: dict = Body(...)):
    """그래프 생성. 세 가지 입력 모드:
      {"transcript": "..."}                      → LLM 추출 (Ollama 필요)
      {"video_path": "..."}                      → STT + LLM 추출 (faster-whisper+Ollama)
      {"concepts": [...], "edges": [[prereq, concept], ...]}  → 직접 구성 (LLM 불필요, 결정적)
    """
    # use_backbone 기본 True: 교육과정 백본으로 LLM 추출 보정 (없으면 자동 무시)
    bb = _BACKBONE if payload.get("use_backbone", True) else None
    if payload.get("concepts"):
        names, edges = payload["concepts"], payload.get("edges", [])
        if bb is not None:
            names, edges = bb.augment(names, edges)
        g = build_graph(names, edges)
    elif payload.get("transcript"):
        from ingest.pipeline import transcript_to_graph  # 지연 import (Ollama)
        g = transcript_to_graph(payload["transcript"],
                                model=payload.get("model", "llama3.1:8b"), backbone=bb)
    elif payload.get("video_path"):
        from ingest.pipeline import video_to_graph        # 지연 import (faster-whisper)
        g = video_to_graph(payload["video_path"],
                           model=payload.get("model", "llama3.1:8b"), backbone=bb)
    elif payload.get("file_path"):
        from ingest.loaders import source_to_graph        # 영상/오디오/PDF/텍스트/자막 통합
        g = source_to_graph(payload["file_path"],
                            model=payload.get("model", "llama3.1:8b"), backbone=bb)
    else:
        raise HTTPException(400, "provide one of: concepts, transcript, video_path, file_path")

    graph_id = uuid.uuid4().hex[:8]
    GRAPHS[graph_id] = g
    return {"graph_id": graph_id, "concepts": _graph_payload(g)}


@app.get("/v1/graph/{graph_id}")
def get_graph(graph_id: str):
    g = _get_graph(graph_id)
    return {"graph_id": graph_id, "concepts": _graph_payload(g)}


@app.post("/v1/recommend")
def recommend(payload: dict = Body(...)):
    """진단 응답(+수준대) → 다음 학습 개념 + 상위 랭킹.
      {"graph_id": "...", "band": "elementary"|null,
       "responses": {"gcd": [0,0,1], ...}, "top_k": 3}
    """
    g = _get_graph(payload.get("graph_id", ""))
    learner = _build_learner(g, payload.get("band"), payload.get("responses", {}))
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    ranked = rec.rank(learner)
    k = int(payload.get("top_k", 3))
    return {
        "next": {"id": ranked[0].concept_id, "name": ranked[0].name,
                 "mastery": ranked[0].mastery},
        "ranking": [
            {"id": r.concept_id, "name": r.name, "score": r.score,
             "mastery": r.mastery, "readiness": r.readiness,
             "remediation": r.remediation}
            for r in ranked[:k]
        ],
    }


@app.post("/v1/path")
def path(payload: dict = Body(...)):
    """목표 개념까지 자기속도 학습 경로 시뮬레이션 (각 단계 통달 가정).
      {"graph_id": "...", "target": "concept_id", "band": null, "responses": {}}
    """
    g = _get_graph(payload.get("graph_id", ""))
    target = payload.get("target")
    if target not in g.ids:
        raise HTTPException(400, f"unknown target: {target}")
    learner = _build_learner(g, payload.get("band"), payload.get("responses", {}))
    rec = Recommender(g, r_star=0.0, W_p=2.0)

    steps = []
    for _ in range(g.n + 1):
        nxt = rec.next_concept(learner)
        steps.append(nxt.name)
        if rec.is_mastered(learner, target):
            break
        learner.update_many(nxt.concept_id, [1, 1, 1, 1, 1, 1])  # 통달 가정
        if nxt.concept_id == target:
            break
    return {"target": g.concepts[g.index(target)].name, "path": steps}


@app.post("/v1/questions")
def questions(payload: dict = Body(...)):
    """개념별 진단 문항 생성 (Ollama 필요).
      {"concept": "약분", "excerpt": "...", "n": 3}
    """
    from ingest.questions import make_questions  # 지연 import (Ollama)
    qs = make_questions(payload["concept"], payload.get("excerpt", ""),
                        n=int(payload.get("n", 3)),
                        model=payload.get("model", "llama3.1:8b"))
    return {"questions": [q.model_dump() for q in qs]}


# ── 종료 제어 (stdin) — PyInstaller 부트로더 PID 함정 회피 ────────────────────
def _stdin_loop():
    for line in sys.stdin:
        if line.strip() == "sidecar shutdown":
            os.kill(os.getpid(), signal.SIGINT)


def main():
    from uvicorn import Config, Server
    threading.Thread(target=_stdin_loop, daemon=True).start()
    server = Server(Config(app, host="127.0.0.1", port=PORT_API, log_level="info"))
    asyncio.run(server.serve())


if __name__ == "__main__":
    main()
