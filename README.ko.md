# pace-tutor

"세상의 진도"가 아니라 **자기 속도로** 학습할 수 있게 돕는 데스크톱 학습 앱.
영상 강의에서 막힌 학습자를 위해, 개념별 수준을 진단하고 **부족한 선수개념을
거슬러 올라가** "아주 기본부터" 다시 시작하는 학습 경로를 자동으로 만든다.

**교과목 무관**(수학/영어/코딩/역사 등 어떤 과목이든) + **수준대별 페이스메이킹**
(초등 / 중·고등 / 대학·성인)을 지원한다. 추천 엔진은 교과목·수준대와 무관하게
보편적이며, 교과목은 `ConceptGraph` 데이터로, 수준대는 `LevelBand`로만 갈린다.

## 현재 상태

✅ **핵심 진단 엔진 구현·검증 완료** (Python 사이드카의 두뇌)
- 개념별 수준진단: Bayesian Knowledge Tracing
- 선수개념 역추적 추천: ALOSI substrategy P/R/C/D

✅ **영상→개념그래프 ingest 파이프라인 구현·검증 완료**
- STT(faster-whisper) → 청킹 → **Ollama 제약 디코딩 2단계 추출** → DAG화/난이도 → `ConceptGraph`
- 환각 차단: `format=schema` + 개념목록 확정 후 그 안에서만 선수관계 추출
- 순환 자동 제거(`break_cycles`)로 DAG 보장 → 엔진과 end-to-end 결합 확인

✅ **사이드카 HTTP API 구현·검증 완료** (`sidecar/server.py`, FastAPI)
- engine+ingest 를 감싼 REST: `/v1/ingest`(자막/영상/직접개념), `/v1/recommend`, `/v1/path`, `/v1/questions`
- stdin `"sidecar shutdown"` 종료(PyInstaller 부트로더 PID 함정 회피) — 실프로세스 검증 완료
- 이 API 가 곧 Tauri UI 가 호출할 계약

✅ **추출 품질 — 측정 + 교육과정 백본** (핵심 신뢰성 확보)
- 측정(`eval_extraction.py`): 로컬 8B 모델은 교과서적 사슬에서도 **선수관계 F1 ~0.33** (기초 엣지 매번 누락) → LLM 단독 신뢰 불가
- 해법(`ingest/backbone.py` + `data/backbone_seed.json`): 표준 개념·검증된 선수관계·별칭 사전.
  LLM 은 "개념↔표준" 매핑만, 선수관계는 백본에서 주입 → **STT 오인식·LLM 엣지 0개에도 완전한 DAG 결정적 보장**
- 매칭 = 정확/별칭(권위) + **보수적 퍼지**(긴 변형만, 오탐 없음) + `coverage()` 리포트(확충 가이드)
- 부정 결과 기록: 로컬 임베딩(nomic-embed-text)은 한국어 개념 매칭 변별력 없음 → 결정적 매칭 채택
- `verify_backbone.py`/`verify_backbone_match.py` 통과. 사이드카 `/v1/ingest`에 `use_backbone` 기본 적용

✅ **React UI 구현·검증 완료** (`ui/`, Vite + React + TS, 라이트테마, 영문 우선 i18n)
- 플로우: 강의 내용 입력 → 개념 그래프 → 수준대·막힌개념 선택 → 학습경로(스테퍼)
- **영문 우선(English-first) + EN/한국어 토글**(`ui/src/i18n.ts`), 로케일별 샘플. 전 세계 사용 대비
- 사이드카(:8008) API 호출. `tsc`+`vite build` 통과, 헤드리스 Chrome 스크린샷으로 EN/KO·플로우·수준대 확인

✅ **Tauri 데스크톱 앱 패키징 완료** (`ui/src-tauri/`)
- Rust 셸(lib.rs)이 Python 사이드카를 spawn/모니터, stdin 종료(부트로더 PID 함정 회피)
- PyInstaller 단일 바이너리(75M) → `.app`에 동봉. `tauri build` 성공: **`pace-tutor.app`(90M) + `.dmg`(80M)** 생성, adhoc 서명
- 사이드카 바이너리 단독 실행 검증(기동·ingest·recommend·종료). 산출물: `ui/src-tauri/target/release/bundle/`

남은 (선택): macOS 공증(배포 시), faster-whisper 번들 내 전사 런타임 검증, 영어 백본 추가, 백본 확충, pyBKT 연동.
※ 런타임 전제: Ollama 데몬(LLM/STT 추출 시) — 직접개념 플로우는 불필요.
설계 근거: [prerequisite-diagnosis-reference.md](prerequisite-diagnosis-reference.md),
[video-to-conceptgraph-reference.md](video-to-conceptgraph-reference.md).

## 구조

```
engine/
  core.py        # ALOSI 순수 수학 함수 (numpy) — 추천 점수, BKT 업데이트
  concepts.py    # 개념 노드 + 선수개념 DAG (순환 검증)
  diagnosis.py   # 학습자 개념별 숙달확률 추적 (BKT) + 수준대 바닥 적용
  recommender.py # "지금 학습할 단 하나의 개념" 추천
  levels.py      # 수준대(초등/중고등/대학·성인) — 바닥·입도·어투
ui/src-tauri/    # Tauri v2 데스크톱 셸 (Rust) — 사이드카 spawn, externalBin 번들
ui/src/i18n.ts   # 영문 우선 i18n (EN/한국어) + 로케일별 샘플
ingest/
  loaders.py     # 영상/오디오/PDF/텍스트/자막 → 텍스트 (통합 진입점 source_to_graph)
  stt.py         # 영상·오디오 → 자막 (faster-whisper)
  chunk.py       # 자막 청킹
  extract.py     # LLM 2단계 추출 (Ollama format=schema 제약 디코딩)
  graph_build.py # 중복제거 + DAG 순환제거 + 난이도 → ConceptGraph
  questions.py   # 개념별 진단 문항 생성
  backbone.py    # 교육과정 백본 — 표준개념 매핑 + 검증된 선수관계 주입
  pipeline.py    # transcript_to_graph / video_to_graph (backbone 지원)
data/
  backbone_seed.json   # 백본 시드(수학 분수·대수 / 과학 물의순환, STT오류 별칭 포함)
sidecar/
  server.py      # FastAPI(:8008) — engine+ingest HTTP API + stdin 종료 + 백본
verify_scenario.py     # 중3 이차방정식 → 기초 역추적 검증
demo_multisubject.py   # 교과목 무관성 + 수준대 페이스메이킹 데모(프로그래밍·영어)
verify_ingest.py       # 자막→그래프 추출 검증(1부 코어 결정적 / 2부 실제 LLM)
verify_sidecar.py      # 사이드카 API 검증(1부 in-process / 2부 실프로세스+stdin종료)
verify_backbone.py     # 백본 검증(결정적) — 노이즈 입력에도 올바른 경로
verify_backbone_match.py # 매칭/커버리지 검증(정확·별칭·보수적 퍼지·coverage)
eval_extraction.py     # LLM 선수관계 추출 품질 측정(one-shot vs 페어와이즈)
```

## 실행 (UI + 사이드카)

```bash
# 1) 사이드카(백엔드)
.venv/bin/python -m sidecar.server   # http://127.0.0.1:8008/docs (Swagger)
# 2) UI (다른 터미널)
cd ui && npm install && npm run dev   # http://localhost:5173
```
(Tauri 데스크톱 빌드는 Rust 설치 후 — tauri-python-sidecar-reference.md 참조)

## 의존성

- Python: `pip install -r requirements.txt`
- 로컬 LLM: [Ollama](https://ollama.com) 데몬 + `ollama pull llama3.1:8b`
- STT: 시스템 `ffmpeg` (영상 디코딩)

## 실행

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python verify_scenario.py
```

## 사용 예

```python
from engine import ConceptGraph, Concept, LearnerState, Recommender

graph = ConceptGraph([
    Concept("gcd", "최대공약수", prereqs=[], difficulty=0.1),
    Concept("reduce_fraction", "약분", prereqs=["gcd"], difficulty=0.2),
    # ...
])
learner = LearnerState(graph)
rec = Recommender(graph, r_star=0.0, W_p=2.0)

learner.update_many("quadratic_equation", [0, 0, 0])  # 이차방정식 다 틀림
print(rec.next_concept(learner).name)  # → "최대공약수" (뿌리 기초로 역추적)
```
