# 영상 → 개념 그래프 자동 생성 파이프라인 — 구현 청사진 (reference)

> 목표: **영상 강의 파일**을 넣으면 → 자막 추출(STT) → 내용 해석 →
> **개념 노드 + 선수개념(prerequisite) DAG + 개념별 진단 문항**을 자동 생성해
> 이미 구현된 `pace-tutor/engine` 의 `ConceptGraph` 로 그대로 투입한다.
> 교과목 무관(수학/영어/코딩/역사…), 로컬 우선(Whisper + Ollama).
>
> 이 문서는 **청사진**이다. 구현은 아직 하지 않는다.

---

## 0. 한 줄 결론

이 파이프라인은 검증된 두 레퍼런스의 **모양만** 빌려오고, 우리 도메인에 맞게 3가지를 바꾼다.

1. **STT** = `SYSTRAN/faster-whisper` (CTranslate2, 세그먼트+단어 타임스탬프). 그대로 사용.
2. **LLM→그래프 파이프라인 모양** = `robert-mcdermott/ai-knowledge-graph` (⭐2.3k, Apache-2.0, 2025-12).
   청크→추출→표준화(중복제거)→연결 의 **5단계 흐름**을 차용.
3. **우리가 바꾸는 결정적 3가지** (이게 청사진의 핵심):
   - 추출을 **일반 SPO 트리플 → "선수개념 전용" 추출**로 교체
   - 취약한 **정규식 JSON 파싱 → Ollama 네이티브 `format=schema` 제약 디코딩**으로 교체 (환각/파싱오류 원천 차단)
   - 레퍼런스에 **없는 DAG 강제(순환 제거)** 를 추가 — 우리 엔진(`ConceptGraph._assert_acyclic`)이 DAG를 요구하기 때문

---

## 1. 레퍼런스 선정 (왜 이걸 골랐나)

| 후보 | 별점/상태 | 라이선스 | 채택? | 이유 |
|---|---|---|---|---|
| **SYSTRAN/faster-whisper** | 표준·활발 | MIT | ✅ STT | CTranslate2로 OpenAI Whisper 대비 ~4배, 메모리↓, CPU/GPU·8bit 양자화. `segment.start/end`, `word_timestamps=True` 제공. 사용자는 이미 Meetily(Whisper계열) 경험. |
| **robert-mcdermott/ai-knowledge-graph** | ⭐2.3k, v0.6.3(2025-12) | Apache-2.0 | ✅ 파이프라인 모양 | OpenAI 호환(Ollama/LM Studio/vLLM) 로컬. 청킹·트리플추출·엔티티표준화·관계추론·시각화의 완성된 5단계. **단, 통째로 쓰지 않고 흐름만 차용.** |
| Microsoft GraphRAG | 인기 높음 | MIT | ❌ 과함 | 대규모 문서 RAG·커뮤니티 요약용. 우리는 영상 1개당 작은 그래프라 무겁고 과함. |
| Neo4j LLM Graph Transformer | 활발 | - | ❌ 불필요 | Neo4j DB 결합. 우리는 SQLite/메모리면 충분. |
| LectureBank / prereq-chain 논문 | 데이터셋·논문 | - | 참고만 | "선수관계 추출"의 학술적 근거. 코드 재사용보다 개념 검증용. |

**결정적 판단**: ai-knowledge-graph를 **라이브러리로 쓰지 않는다**. 그 repo의 **파이프라인 설계(5단계)와 프롬프트 전략**만 학습해, 우리 `engine/`에 맞는 **얇은 새 모듈**(`ingest/`)로 다시 쓴다. 이유는 §4의 "결정적 차이".

---

## 2. 매핑표 — 레퍼런스 ↔ 우리 파이프라인

| ai-knowledge-graph (레퍼런스) | 우리 대응 | 비고 |
|---|---|---|
| 입력: 텍스트 문서 | **영상 → faster-whisper 자막** | STT 단계가 우리 앞단에 추가됨 |
| Stage1: `chunk_text(text, size, overlap)` | **자막 청킹** (단어수 기준, overlap) | 거의 그대로 차용 |
| Stage2: SPO 트리플 추출 프롬프트 | **2단계 추출**: ①개념 목록 → ②선수관계 | SPO 대신 prerequisite 전용 |
| `extract_json_from_text()` 정규식 복구 | **Ollama `format=schema`** | ⚠️ 교체 — §3,§6-1 |
| Stage3: `standardize_entities()` | **개념 중복제거/정규화** | 차용 + 우리 표시명 보존 |
| Stage4: `infer_relationships()` (커뮤니티 연결) | (대부분) **불필요** | 작은 그래프라 transitive만 선택 사용 |
| Stage5: 시각화 HTML | **불필요** (Tauri UI가 별도) | |
| 출력: 트리플 리스트 | **`ConceptGraph([Concept(id,name,prereqs,difficulty)])`** | 우리 엔진 입력 형식 |
| (없음) | **DAG 순환 제거** | 우리가 추가 — §3-C |
| (없음) | **난이도/진단문항 생성** | 우리가 추가 — §3-D,E |

대상 출력 형식(우리 엔진, 이미 구현됨): `pace-tutor/engine/concepts.py`
```python
Concept(id="reduce_fraction", name="약분", prereqs=["gcd"], difficulty=0.2, grade="초5")
ConceptGraph([...])  # 생성 시 _assert_acyclic() 로 순환 자동 검증
```

---

## 3. 파이프라인 단계별 — 복붙용 코드

새 모듈 구조 (제안): `pace-tutor/ingest/`
```
ingest/
  stt.py        # 영상 → 자막 (faster-whisper)
  chunk.py      # 자막 청킹 (레퍼런스 차용)
  extract.py    # LLM 2단계 추출 (Ollama 제약 디코딩)
  graph_build.py# 중복제거 + DAG 강제 + difficulty + Concept 변환
  questions.py  # 개념별 진단 문항 생성
  pipeline.py   # 전체 오케스트레이션
```

### A. STT — 영상 → 자막 (faster-whisper, 그대로)

```python
# ingest/stt.py
from faster_whisper import WhisperModel

def transcribe(video_path: str, model_size: str = "base") -> str:
    # Apple Silicon: compute_type="int8" 로 가볍게. 정확도 필요하면 "small"/"medium".
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(video_path, word_timestamps=True)
    # 타임스탬프는 나중에 "이 개념은 영상 12:30 구간" 링크에 사용
    return " ".join(seg.text for seg in segments)
```
> faster-whisper는 ffmpeg로 오디오를 읽으므로 mp4/mkv 등 영상 직접 입력 가능(ffmpeg 설치 필요).

### B. 청킹 (레퍼런스 `text_utils.py:chunk_text` 차용)

```python
# ingest/chunk.py  — 출처: ai-knowledge-graph text_utils.py (단어수 기준 overlap)
def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> list[str]:
    words = text.split()
    if len(words) <= chunk_size:
        return [text]
    chunks, start = [], 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks
```

### C. 🔑 추출 — Ollama 제약 디코딩으로 환각 차단 (2단계)

레퍼런스는 자유 텍스트→정규식 파싱(취약). 우리는 **Pydantic 스키마 = `format`** 으로 LLM 출력을 JSON 구조에 강제한다.

```python
# ingest/extract.py
from ollama import chat
from pydantic import BaseModel

# --- 1단계: 청크에서 '개념 목록'만 뽑는다 (원자적 개념) ---
class ConceptList(BaseModel):
    concepts: list[str]   # 사람이 읽는 개념명 (예: "약분", "최대공약수")

CONCEPT_SYS = (
    "너는 강의 자막에서 학습 '개념(concept)'만 원자적으로 추출하는 도구다. "
    "개념은 가르치고 평가할 수 있는 최소 학습 단위여야 한다. "
    "자막에 실제로 등장/전제된 개념만 뽑고, 없는 것은 지어내지 마라."
)

def extract_concepts(chunk: str, model="gemma3") -> list[str]:
    r = chat(
        model=model,
        messages=[{"role": "system", "content": CONCEPT_SYS},
                  {"role": "user", "content": f"자막:\n```\n{chunk}\n```"}],
        format=ConceptList.model_json_schema(),   # ← 제약 디코딩
        options={"temperature": 0},               # ← 추출은 반드시 0
    )
    return ConceptList.model_validate_json(r.message.content).concepts


# --- 2단계: '이미 확정된 개념 집합' 안에서만 선수관계를 묻는다 ---
#     (새 개념을 못 만들게 해서 환각을 구조적으로 차단)
class PrereqEdge(BaseModel):
    concept: str       # 후속 개념 (반드시 아래 개념목록 중 하나)
    prerequisite: str  # 선수 개념 (반드시 아래 개념목록 중 하나)

class PrereqEdges(BaseModel):
    edges: list[PrereqEdge]

PREREQ_SYS = (
    "너는 주어진 '개념 목록' 안에서만 선수개념 관계를 찾는 도구다. "
    "'A를 배우려면 B를 먼저 알아야 한다'가 명백할 때만 (concept=A, prerequisite=B) 엣지를 만든다. "
    "목록에 없는 개념은 절대 쓰지 마라. 자기 자신을 선수개념으로 두지 마라. "
    "확신이 없으면 엣지를 만들지 마라(거짓 엣지보다 누락이 낫다)."
)

def extract_prereqs(concepts: list[str], model="gemma3") -> list[PrereqEdge]:
    listing = "\n".join(f"- {c}" for c in concepts)
    r = chat(
        model=model,
        messages=[{"role": "system", "content": PREREQ_SYS},
                  {"role": "user", "content": f"개념 목록:\n{listing}"}],
        format=PrereqEdges.model_json_schema(),
        options={"temperature": 0},
    )
    edges = PrereqEdges.model_validate_json(r.message.content).edges
    # 방어적 필터: 목록 밖 개념/자기참조 제거 (LLM이 어겨도 무력화)
    cset = set(concepts)
    return [e for e in edges
            if e.concept in cset and e.prerequisite in cset
            and e.concept != e.prerequisite]
```

### D. 그래프 빌드 — 중복제거 + 난이도 + **DAG 강제(순환 제거)**

레퍼런스에 **없는** 핵심. 우리 엔진은 순환이면 생성 자체가 실패하므로, 투입 전에 끊는다.

```python
# ingest/graph_build.py
import re
from engine import Concept, ConceptGraph

def _key(name: str) -> str:
    # 표시명은 보존, 내부 id는 정규화 (레퍼런스 standardize_entities 아이디어 차용)
    return re.sub(r"\s+", "_", name.strip().lower())

def break_cycles(nodes: list[str], edges: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """DFS로 back-edge(순환 유발 엣지)를 찾아 제거 → DAG 보장.
    edges: (prerequisite, concept) = (from, to)  방향: 선수 → 후속
    """
    from collections import defaultdict
    succ = defaultdict(list)
    for a, b in edges:
        succ[a].append(b)
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    keep, removed = [], set()

    def dfs(u):
        color[u] = GRAY
        for v in succ[u]:
            if (u, v) in removed:
                continue
            if color[v] == GRAY:        # back-edge = 순환 → 제거
                removed.add((u, v))
            elif color[v] == WHITE:
                dfs(v)
        color[u] = BLACK

    for n in nodes:
        if color[n] == WHITE:
            dfs(n)
    return [(a, b) for (a, b) in edges if (a, b) not in removed]

def assign_difficulty(nodes, edges) -> dict[str, float]:
    """위상 깊이(=선수개념 사슬 길이)를 0~1 난이도로 매핑.
    뿌리(선수개념 없음)=쉬움, 깊을수록 어려움. LLM 난이도가 있으면 평균내도 됨.
    """
    from collections import defaultdict, deque
    indeg = {n: 0 for n in nodes}
    succ = defaultdict(list)
    for a, b in edges:          # a=prereq → b=concept
        indeg[b] += 1
        succ[a].append(b)
    depth = {n: 0 for n in nodes}
    q = deque([n for n in nodes if indeg[n] == 0])
    while q:
        u = q.popleft()
        for v in succ[u]:
            depth[v] = max(depth[v], depth[u] + 1)
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    maxd = max(depth.values()) or 1
    return {n: round(0.1 + 0.8 * depth[n] / maxd, 2) for n in nodes}

def build_graph(concept_names: list[str], prereq_edges) -> ConceptGraph:
    # 1) 정규화 + 중복제거 (key 기준)
    name_by_key = {}
    for nm in concept_names:
        name_by_key.setdefault(_key(nm), nm)
    nodes = list(name_by_key)
    # 2) 엣지를 (prereq_key, concept_key) 로, key 기준 변환
    raw = [( _key(e.prerequisite), _key(e.concept) ) for e in prereq_edges]
    raw = [(a, b) for (a, b) in raw if a in name_by_key and b in name_by_key and a != b]
    raw = list(set(raw))
    # 3) 순환 제거 → DAG
    dag = break_cycles(nodes, raw)
    # 4) 난이도
    diff = assign_difficulty(nodes, dag)
    # 5) Concept 변환 (prereqs = 그 개념의 선수 key 목록)
    from collections import defaultdict
    prereqs_of = defaultdict(list)
    for a, b in dag:            # a=prereq → b=concept
        prereqs_of[b].append(a)
    concepts = [Concept(id=k, name=name_by_key[k],
                        prereqs=prereqs_of[k], difficulty=diff[k])
                for k in nodes]
    return ConceptGraph(concepts)   # 생성 시 _assert_acyclic() 재검증 (이중 안전망)
```

### E. 진단 문항 생성 (개념별)

```python
# ingest/questions.py
from ollama import chat
from pydantic import BaseModel

class Question(BaseModel):
    stem: str
    choices: list[str]
    answer_index: int

class QuestionSet(BaseModel):
    questions: list[Question]

def make_questions(concept_name: str, transcript_excerpt: str, n=3, model="gemma3"):
    sys = ("개념 하나의 숙달 여부를 가릴 4지선다 진단 문항을 만든다. "
           "정답은 1개. 보기는 그럴듯한 오답 포함. 자막 범위를 벗어나지 마라.")
    r = chat(model=model,
        messages=[{"role":"system","content":sys},
                  {"role":"user","content":f"개념: {concept_name}\n참고자막:\n{transcript_excerpt}\n문항 {n}개"}],
        format=QuestionSet.model_json_schema(),
        options={"temperature": 0.3})   # 문항은 약간의 다양성 허용
    return QuestionSet.model_validate_json(r.message.content).questions
```

---

## 4. 결정적 차이 — 우리는 레퍼런스보다 단순/복잡한 지점

| 항목 | ai-knowledge-graph | 우리 | 그래서 |
|---|---|---|---|
| JSON 획득 | 자유생성 + 정규식/괄호카운팅 복구(`extract_json_from_text`) | **Ollama `format=schema` 제약 디코딩** | 파싱 실패·환각 **구조적으로 제거** (더 단순+견고) |
| 관계 종류 | 임의 술어(predicate ≤3단어) | **단일 관계 = prerequisite** | 술어 정규화 로직 전부 **불필요** |
| 환각 방지 | 사후 표준화 | **개념목록 먼저 확정 → 그 안에서만 엣지** | 새 개념 생성 봉쇄 (더 안전) |
| 그래프 형태 | 무방향/임의 방향, 순환 허용 | **방향성 DAG 필수** | **순환 제거 단계 추가**(레퍼런스에 없음) |
| 난이도 | 없음 | **위상 깊이 기반 difficulty** | 우리 엔진 입력에 필요 |
| 규모 | 대형 문서 전체 KG | **영상 1개당 수십~수백 개념** | community 추론·시각화 **불필요** |
| temperature | 0.8 (config 기본) | **0.0 (추출)** | 추출 일관성 ↑ (레퍼런스 기본값은 위험) |
| 저장 | - | SQLite/JSON | 가벼움 |

---

## 5. 함정(gotcha) — 레퍼런스 소스에서 직접 확인한 것들

1. **레퍼런스 JSON 파싱은 취약하다**: `llm.py:extract_json_from_text`는 ```` ```json ```` 블록 추출 → 괄호 카운팅 → 정규식으로 키 따옴표/trailing comma 수선까지 한다. 즉 **모델이 형식을 자주 틀린다는 방증**. → 우리는 `format=schema`로 회피(§3-C). 단, **로컬 모델이 작으면 스키마를 어겨도 빈/이상 출력**이 날 수 있으니 `model_validate_json` 실패 시 1회 재시도 + 방어 필터(§3-C 끝)는 필수.

2. **config 기본 temperature=0.8**(`config.toml`): 추출엔 너무 높다. Ollama 공식 문서도 추출은 `temperature=0` 권장. 반드시 0으로.

3. **chunk_size 불일치**: `config.toml`은 100단어, `text_utils.py` 기본은 500단어로 서로 다르다. 강의 자막은 한 청크에 한 주제가 담기도록 **300~500단어 + overlap 50** 권장. 너무 작으면 선수관계 문맥이 끊기고, 너무 크면 작은 로컬모델이 개념을 놓친다.

4. **전부 소문자 강제**(`main_prompts.py`: "Make all the text ... lower-case"): 영어 KG엔 맞지만 우리는 **표시명(한글/대소문자) 보존 + 내부 id만 정규화**해야 한다(§3-D `_key` vs `name`). 레퍼런스 프롬프트를 그대로 베끼면 "약분"이 깨진다.

5. **자기참조 트리플 제거**(`entity_standardization.py:176`): 레퍼런스도 `subject==object`를 지운다. 우리도 자기 자신을 선수개념으로 두는 엣지를 반드시 제거(§3-C 필터, §3-D `a != b`).

6. **순환은 반드시 생긴다**: 청크별로 따로 추출하면 "A는 B의 선수, B는 A의 선수" 모순이 합쳐질 때 순환이 난다. 우리 엔진 `ConceptGraph` 생성자가 순환이면 `ValueError`를 던지므로, **투입 전 `break_cycles` 필수**(§3-D). DFS back-edge 제거로 충분.

7. **청크 간 개념 중복**: overlap 때문에 같은 개념이 여러 청크에서 나온다. key 정규화로 합치되(§3-D), 2단계 선수관계는 **전체 합친 개념 집합**에 대해 한 번에 묻는 게 일관적(청크마다 따로 물으면 엣지가 파편화).

8. **faster-whisper는 ffmpeg 의존**: 영상 파일 디코딩에 ffmpeg 필요. Tauri 번들에 포함하거나 사용자 환경 확인. 큰 모델(medium/large)은 메모리·시간↑ → 데스크톱 기본은 `base`/`small`+`int8`.

---

## 6. 실행 순서 체크리스트

- [ ] 의존성: `pip install faster-whisper ollama pydantic` (+ 시스템 ffmpeg, Ollama 데몬 + `ollama pull gemma3`)
- [ ] `ingest/stt.py`: 영상 → 자막 텍스트(+타임스탬프 보관) — faster-whisper `int8`
- [ ] `ingest/chunk.py`: 레퍼런스 `chunk_text` 차용 (400/50)
- [ ] `ingest/extract.py`: **2단계** 추출 — ①개념목록 → ②목록 내 선수관계, 둘 다 `format=schema` + `temperature=0` + 방어필터
- [ ] `ingest/graph_build.py`: key 정규화·중복제거 → `break_cycles`(DAG) → `assign_difficulty` → `Concept`/`ConceptGraph` 변환
- [ ] `ingest/questions.py`: 개념별 진단 문항 (선택)
- [ ] `ingest/pipeline.py`: 영상경로 → `ConceptGraph` 반환하는 end-to-end 함수
- [ ] **검증 1 (구조)**: 임의 강의 자막으로 돌려 `ConceptGraph` 가 예외 없이 생성되는지(=DAG 보장) 확인
- [ ] **검증 2 (의미)**: 생성된 그래프를 `engine.Recommender`에 넣어, 막힌 개념에서 기초로 역추적되는지 (이미 검증된 엔진과 결합) — 교과목 2개 이상으로
- [ ] **검증 3 (환각)**: 개념·엣지가 자막에 실재하는지 표본 점검. 거짓 엣지율 측정 → 높으면 PREREQ_SYS 강화/모델 상향
- [ ] (별도) Tauri UI·사이드카 번들링은 `/refbuild Tauri Python sidecar` 청사진으로 분리
- [ ] (선택) 개념 백본: 한국 교육과정 성취기준 사전을 두고 LLM은 "자막개념 ↔ 표준개념 매핑"만 시켜 환각 추가 억제

---

## 7. 참고한 레퍼런스 실제 파일

- `robert-mcdermott/ai-knowledge-graph` (⭐2.3k, Apache-2.0, v0.6.3 2025-12)
  - `src/knowledge_graph/prompts/main_prompts.py` — SPO 추출 프롬프트 전략(개념 일관성·원자성·대명사 치환)
  - `src/knowledge_graph/llm.py` — `call_llm`(OpenAI호환/Ollama), `extract_json_from_text`(취약한 정규식 파싱 → 우리는 교체)
  - `src/knowledge_graph/text_utils.py:chunk_text` — 단어수 기준 overlap 청킹(차용)
  - `src/knowledge_graph/entity_standardization.py` — `standardize_entities`(변형 그룹핑·대표명 선택), 자기참조 제거(차용/각색)
  - `config.toml` — model/base_url(Ollama), chunk_size/overlap, temperature 기본값(함정 §5-2,3)
- `SYSTRAN/faster-whisper` (MIT) — `WhisperModel.transcribe(..., word_timestamps=True)`, `segment.start/end`
- Ollama 구조화 출력 — `format=Model.model_json_schema()` + `options={"temperature":0}` + `Model.model_validate_json()` (제약 디코딩)
- 학술 근거(참고만): LectureBank / prerequisite chain learning — 선수관계 추출의 타당성
