"""🔑 LLM 추출 — Ollama 제약 디코딩으로 환각 차단 (2단계).

레퍼런스(ai-knowledge-graph)는 자유생성+정규식 파싱(취약). 우리는 Pydantic 스키마를
Ollama `format` 으로 강제(제약 디코딩)해 파싱 실패·환각을 구조적으로 제거한다.

2단계 전략(청사진 §3-C):
  1) 청크에서 '개념 목록'만 추출 (원자적 개념)
  2) 확정된 개념 집합 *안에서만* 선수관계 엣지를 묻는다 → 새 개념 생성 봉쇄

기본 모델은 llama3.1:8b (로컬). 추출은 temperature=0.
"""

from __future__ import annotations

from collections import Counter

from ollama import chat
from pydantic import BaseModel

DEFAULT_MODEL = "llama3.1:8b"


def detect_lang(text: str) -> str:
    """자막 언어 추정(개념 출력 언어 강제용). 한글 비율로 ko/en 판정."""
    han = sum(1 for c in text if "가" <= c <= "힣")
    letters = sum(1 for c in text if c.isalpha())
    if letters and han / letters > 0.15:
        return "Korean"
    return "English"


# --- 1단계: 개념 목록 ---------------------------------------------------------
class ConceptList(BaseModel):
    concepts: list[str]


CONCEPT_SYS = (
    "You extract atomic learning 'concepts' from a lecture transcript. "
    "A concept is the smallest teachable/testable unit. "
    "Only extract concepts actually present or clearly assumed in the text; never invent. "
    "Each concept is a short noun phrase."
)


def extract_concepts(chunk: str, model: str = DEFAULT_MODEL,
                     lang: str | None = None) -> list[str]:
    lang = lang or detect_lang(chunk)
    # 출력 언어를 명시적으로 강제 — 자막이 영어면 개념도 영어로(과거 한국어로 새던 문제 해결)
    directive = (f"IMPORTANT: Write every concept name in {lang} only "
                 f"(the same language as the transcript).")
    r = chat(
        model=model,
        messages=[
            {"role": "system", "content": CONCEPT_SYS},
            {"role": "user", "content": f"{directive}\n\nTranscript:\n```\n{chunk}\n```\n"
                                        f"Extract the learning concepts."},
        ],
        format=ConceptList.model_json_schema(),
        options={"temperature": 0},
    )
    out = ConceptList.model_validate_json(r.message.content).concepts
    # 공백 제거 + 중복 제거(순서 보존)
    seen, clean = set(), []
    for c in out:
        c = c.strip()
        if c and c.lower() not in seen:
            seen.add(c.lower())
            clean.append(c)
    return clean


# --- 2단계: 선수관계 엣지 (개념 목록 내부에서만) ------------------------------
class PrereqEdge(BaseModel):
    concept: str       # 후속 개념
    prerequisite: str  # 선수 개념


class PrereqEdges(BaseModel):
    edges: list[PrereqEdge]


PREREQ_SYS = (
    "너는 주어진 '개념 목록' 안에서만 선수개념 관계를 찾는 도구다. "
    "'A를 배우려면 B를 먼저 알아야 한다'가 명백할 때만 (concept=A, prerequisite=B) 엣지를 만든다. "
    "목록에 없는 개념은 절대 쓰지 마라. 자기 자신을 선수개념으로 두지 마라. "
    "확신이 없으면 엣지를 만들지 마라(거짓 엣지보다 누락이 낫다)."
)


def extract_prereqs(concepts: list[str], model: str = DEFAULT_MODEL) -> list[PrereqEdge]:
    if len(concepts) < 2:
        return []
    listing = "\n".join(f"- {c}" for c in concepts)
    r = chat(
        model=model,
        messages=[
            {"role": "system", "content": PREREQ_SYS},
            {"role": "user", "content": f"개념 목록:\n{listing}\n\n이 목록 안에서 선수개념 관계를 찾아라."},
        ],
        format=PrereqEdges.model_json_schema(),
        options={"temperature": 0},
    )
    edges = PrereqEdges.model_validate_json(r.message.content).edges
    # 방어 필터: 목록 밖 개념/자기참조 제거 (LLM이 어겨도 무력화) — 청사진 §3-C
    cset = {c.lower() for c in concepts}
    return [
        e for e in edges
        if e.concept.lower() in cset and e.prerequisite.lower() in cset
        and e.concept.strip().lower() != e.prerequisite.strip().lower()
    ]


# --- 2단계(개선): 개념별 '페어와이즈' 선수관계 질의 ---------------------------
#   "전체 엣지를 한 번에" 묻는 one-shot 은 희소 추출(낮은 recall)이 잦다.
#   개념 X 하나에 집중해 "X의 직접 선수개념은?"을 따로 물으면 recall 이 크게 오른다
#   (LectureBank 류 concept-pair 분류 방식). 다중 샘플 다수결로 분산도 줄인다.
class PrereqsOf(BaseModel):
    prerequisites: list[str]


PAIRWISE_SYS = (
    "너는 한 개념의 선수개념을 찾는 도구다. "
    "선수개념 = 그 개념을 제대로 배우기 전에 먼저 이해하고 있어야 하는 개념. "
    "반드시 주어진 목록 안에서만 고른다. 그 개념의 기초가 되는 것은 빠짐없이 포함하고, "
    "명백히 무관한 것만 제외한다.\n"
    "예) 목록[최대공약수, 약분, 분수의 덧셈] 에서 "
    "'약분'의 선수개념 → [최대공약수], '분수의 덧셈'의 선수개념 → [약분]."
)


def extract_prereqs_pairwise(concepts: list[str], model: str = DEFAULT_MODEL,
                             samples: int = 1, min_votes: int | None = None) -> list[PrereqEdge]:
    """개념별로 직접 선수개념을 질의 → 엣지. samples>1 이면 다수결.

    :param samples: 같은 질의를 몇 번 반복할지 (분산↓, recall↑)
    :param min_votes: 엣지 채택 최소 득표(기본=과반). samples=1 이면 1.
    """
    if len(concepts) < 2:
        return []
    by_lower = {c.lower(): c for c in concepts}
    thresh = min_votes if min_votes is not None else (samples // 2 + 1)
    votes: Counter[tuple[str, str]] = Counter()

    for s in range(samples):
        for target in concepts:
            others = [c for c in concepts if c != target]
            listing = "\n".join(f"- {c}" for c in others)
            r = chat(
                model=model,
                messages=[
                    {"role": "system", "content": PAIRWISE_SYS},
                    {"role": "user", "content":
                        f"개념 목록:\n{listing}\n\n"
                        f"위 목록 중 '{target}'의 **직접** 선수개념만 고르시오. 없으면 빈 목록."},
                ],
                format=PrereqsOf.model_json_schema(),
                options={"temperature": 0.0 if samples == 1 else 0.4},
            )
            for p in PrereqsOf.model_validate_json(r.message.content).prerequisites:
                pl = p.strip().lower()
                if pl in by_lower and pl != target.lower():
                    votes[(by_lower[pl], target)] += 1

    return [PrereqEdge(prerequisite=a, concept=b)
            for (a, b), v in votes.items() if v >= thresh]


def extract_all(chunks: list[str], model: str = DEFAULT_MODEL,
                pairwise: bool = False, samples: int = 1):
    """여러 청크 → (전체 개념 목록, 선수관계 엣지).

    개념은 청크별로 모아 합치고(중복 제거), 선수관계는 합친 전체 집합에 대해
    한 번에 묻는다(청크별로 따로 물으면 엣지가 파편화 — 청사진 §5-7).

    :param pairwise: True 면 개념별 페어와이즈 질의(권장, recall↑). False 면 one-shot.
    :param samples: 페어와이즈 다중 샘플 수(분산↓).
    """
    all_concepts: list[str] = []
    seen: set[str] = set()
    for ch in chunks:
        for c in extract_concepts(ch, model=model):
            if c.lower() not in seen:
                seen.add(c.lower())
                all_concepts.append(c)
    if pairwise:
        edges = extract_prereqs_pairwise(all_concepts, model=model, samples=samples)
    else:
        edges = extract_prereqs(all_concepts, model=model)
    return all_concepts, edges
