"""교육과정 백본 사전 — LLM 추출의 신뢰도를 끌어올리는 결정적 경로.

배경(eval_extraction.py 측정): 로컬 8B 모델은 교과서적 선수관계 사슬에서도 F1 ~0.33,
'최대공약수→약분' 같은 기초 엣지를 매번 놓친다. LLM 단독은 신뢰 불가.

해법: 표준 교육과정을 백본으로 두고, **LLM 은 "자막 개념 ↔ 표준 개념" 매핑만** 하게 한다.
선수관계(엣지)는 LLM 이 지어내는 대신 백본에서 가져온다(검증된 구조 = 결정적).
백본에 없는(=새로운) 개념은 LLM 엣지를 보조로 유지한다.

매핑은 별칭(aliases)으로 STT 오인식("응결"→"은결")·표기 변형까지 흡수한다.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher


def _norm(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().lower())


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


@dataclass
class BackboneConcept:
    id: str
    name: str
    prereqs: list[str] = field(default_factory=list)   # 표준 id 목록
    aliases: list[str] = field(default_factory=list)    # 표기 변형/STT 오인식 포함
    difficulty: float | None = None
    grade: str = ""
    # 큐레이션 진단 문항(정답 키 신뢰 가능). 각 항목: {stem, choices, answer(index)}
    # 로컬 LLM 자동생성은 정답 키가 틀려서(측정됨) 쓰지 않는다 — 객관 채점은 이 문항으로.
    questions: list = field(default_factory=list)


class Backbone:
    """표준 개념 + 검증된 선수관계 + 별칭. 추출 결과를 표준에 정렬한다."""

    def __init__(self, concepts: list[BackboneConcept]):
        self.concepts = concepts
        self._by_id = {c.id: c for c in concepts}
        # 정규화된 surface form → 표준 id (이름·별칭 모두 등록)
        self._lookup: dict[str, str] = {}
        for c in concepts:
            # 표시명·별칭만 매칭 키로 등록. 내부 id(영문)는 surface form 이 아니므로 제외
            # (등록하면 영어 입력이 한국어 표시명으로 잘못 치환됨 — 다국어 누수 방지)
            self._lookup[_norm(c.name)] = c.id
            for a in c.aliases:
                self._lookup[_norm(a)] = c.id

    @classmethod
    def from_json(cls, path: str) -> "Backbone":
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls([BackboneConcept(**d) for d in data])

    @classmethod
    def from_jsons(cls, paths) -> "Backbone":
        """여러 백본 파일(언어별 등)을 하나로 병합. id 는 파일 간 고유해야 함.

        다른 언어 개념은 표기(스크립트)가 달라 매칭 충돌이 없으므로,
        영어/한국어 콘텐츠가 각자 자기 언어 백본에 자연히 정렬된다.
        """
        concepts: list[BackboneConcept] = []
        seen_ids: set[str] = set()
        for p in paths:
            with open(p, encoding="utf-8") as f:
                for d in json.load(f):
                    if d["id"] in seen_ids:
                        raise ValueError(f"중복 백본 id: {d['id']} ({p})")
                    seen_ids.add(d["id"])
                    concepts.append(BackboneConcept(**d))
        return cls(concepts)

    def match(self, surface_name: str, fuzzy: bool = False,
              fuzzy_threshold: float = 0.7, margin: float = 0.08) -> str | None:
        """추출된 개념명을 표준 id 로 매핑.

        1) 정확/별칭 매칭(정규화) — 권위, 항상 우선.
        2) fuzzy=True 면 보조로 편집거리 매칭 — 단, **보수적**으로만.
           짧은 한국어 단어는 한 글자 오류와 무관 단어의 구분이 안 되므로
           (예: '미분'~'약분' 0.50), 높은 임계(기본 0.7) + 2위와의 마진을 요구한다.
           → 띄어쓰기·긴 패러프레이즈(예: '증발현상'→'증발')는 잡고, 한 글자 STT
             오류(예: '은결'→'응결')는 못 잡는다(그건 별칭으로 커버해야 함).
        """
        exact = self._lookup.get(_norm(surface_name))
        if exact or not fuzzy:
            return exact
        scored = sorted(
            ((_ratio(surface_name, surf), cid) for surf, cid in self._lookup.items()),
            reverse=True,
        )
        if not scored:
            return None
        best_r, best_id = scored[0]
        second_r = scored[1][0] if len(scored) > 1 else 0.0
        if best_r >= fuzzy_threshold and (best_r - second_r) >= margin:
            return best_id
        return None

    def questions_for(self, name: str, fuzzy: bool = True) -> list:
        """개념명에 대한 큐레이션 문항 목록(정답 키 신뢰). 없으면 빈 목록.

        반환 항목: {stem, choices, answer_index}
        """
        cid = self.match(name, fuzzy=fuzzy)
        if not cid:
            return []
        out = []
        for q in self._by_id[cid].questions:
            out.append({
                "stem": q["stem"],
                "choices": q["choices"],
                "answer_index": q.get("answer", q.get("answer_index", 0)),
            })
        return out

    def coverage(self, concept_names, fuzzy: bool = False) -> dict:
        """추출 개념들의 백본 커버리지 리포트 — 백본 확충 워크플로우용.

        :return: {"matched": [(원본, 표준명)...], "novel": [원본...], "rate": 0~1}
        """
        matched, novel = [], []
        for nm in concept_names:
            cid = self.match(nm, fuzzy=fuzzy)
            if cid:
                matched.append((nm, self._by_id[cid].name))
            else:
                novel.append(nm)
        total = len(concept_names) or 1
        return {"matched": matched, "novel": novel,
                "rate": round(len(matched) / total, 2)}

    def augment(self, concept_names, llm_edges, fuzzy: bool = False):
        """추출 개념 + LLM 엣지 → (표준 정렬된 개념명 목록, (선수, 후속) 엣지쌍 목록).

        - 백본에 매칭된 개념: 표준 이름으로 치환 + 백본의 검증된 선수관계 주입
          (단, 양끝이 모두 이번 그래프에 존재하는 엣지만)
        - 매칭 안 된 개념: 원래 이름 유지 + 관련 LLM 엣지 보조 유지
        - fuzzy=True 면 매칭에 보수적 편집거리 보조 사용(match 참고)
        """
        def _match(n):
            return self.match(n, fuzzy=fuzzy)
        # 1) 표준 매핑
        canonical_name: dict[str, str] = {}   # 출력에 쓸 이름 (표준 or 원본)
        matched_ids: set[str] = set()
        present_names: list[str] = []
        seen: set[str] = set()

        def _add(name: str):
            key = _norm(name)
            if key not in seen:
                seen.add(key)
                present_names.append(name)

        name_to_output: dict[str, str] = {}  # 원본명 → 출력명
        for nm in concept_names:
            cid = _match(nm)
            if cid:
                out = self._by_id[cid].name
                matched_ids.add(cid)
                name_to_output[nm] = out
            else:
                out = nm.strip()
                name_to_output[nm] = out
            _add(out)

        present_ids = matched_ids
        id_to_name = {cid: self._by_id[cid].name for cid in present_ids}
        present_output_names = {n for n in present_names}

        # 2) 백본 선수관계 주입 (양끝 모두 present 인 경우만) — 결정적, 신뢰됨
        edges: set[tuple[str, str]] = set()
        for cid in present_ids:
            for pid in self._by_id[cid].prereqs:
                if pid in present_ids:
                    edges.add((id_to_name[pid], id_to_name[cid]))

        # 3) 매칭 안 된 개념이 끼는 LLM 엣지만 보조로 유지 (백본 미지원 영역 보완)
        for e in llm_edges:
            a_raw = e[0] if isinstance(e, (tuple, list)) else e.prerequisite
            b_raw = e[1] if isinstance(e, (tuple, list)) else e.concept
            a = name_to_output.get(a_raw, a_raw.strip())
            b = name_to_output.get(b_raw, b_raw.strip())
            a_matched = _match(a_raw) is not None
            b_matched = _match(b_raw) is not None
            # 양끝 다 백본 매칭이면 백본 구조가 권위 — LLM 엣지는 무시
            if a_matched and b_matched:
                continue
            if a in present_output_names and b in present_output_names and _norm(a) != _norm(b):
                edges.add((a, b))

        return present_names, sorted(edges)
