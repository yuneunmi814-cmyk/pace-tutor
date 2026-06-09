# Contributing to pace-tutor

First off — **thank you** 🙌 pace-tutor exists to help anyone learn *at their own pace,
from the basics up*. Every subject you add, every question you write, every bug you
report makes that real for more learners. You don't need to be an expert to help.

This guide is designed so your **first contribution takes ~5 minutes**.

[한국어 안내는 아래 ↓](#한국어-요약)

---

## Ways to contribute (easiest first)

| | What | Code needed? |
|---|---|---|
| 🟢 **Add a subject** | A curriculum backbone (concepts + prerequisites) as one JSON file | **None** — just data |
| 🟢 **Add quiz questions** | Curated questions for existing concepts | None — just data |
| 🟢 **Translate / fix wording** | UI strings, README, concept names in your language | A little |
| 🟡 **Report a bug / idea** | Open an issue (what you did, what happened, what you expected) | None |
| 🟡 **Improve the UI** | React + light theme (`ui/`) | Frontend |
| 🔴 **Engine / pipeline** | Diagnosis, extraction, STT (`engine/`, `ingest/`) | Python |

> ⭐ **The single most valuable contribution is a curriculum backbone.** The diagnosis
> engine is subject-agnostic — it already works for *any* topic. What it needs is reliable
> "what comes before what" maps. A local LLM can't be trusted for that (we measured it),
> so curated backbones are the heart of the project. **If you know a subject, you can teach the app.**

---

## 🟢 Your first PR: add a subject (just one JSON file)

A "backbone" is a list of concepts, each with its prerequisites. That's it.

**1. Create `data/backbone_<subject>_<lang>.json`** (e.g. `data/backbone_music_en.json`):

```json
[
  {"id": "mus_pitch", "name": "Pitch", "prereqs": [], "aliases": ["notes", "pitches"], "grade": "Beginner",
    "questions": [
      {"stem": "Which note is higher in pitch?", "choices": ["A5", "A3", "A4", "A2"], "answer": 0}
    ]},
  {"id": "mus_scale", "name": "Scales", "prereqs": ["mus_pitch"], "aliases": ["scale", "major scale"]},
  {"id": "mus_chord", "name": "Chords", "prereqs": ["mus_scale"], "aliases": ["chord", "triads"]},
  {"id": "mus_progression", "name": "Chord Progressions", "prereqs": ["mus_chord"], "aliases": ["progressions"]}
]
```

**Field reference**
- `id` *(required)* — globally unique, lowercase, prefix by subject (`mus_…`) so it never collides.
- `name` *(required)* — the display name learners see (any language).
- `prereqs` — list of `id`s that must be learned **before** this concept. Keep it a DAG (no cycles).
- `aliases` — alternate phrasings / common spellings / typos so messy lecture transcripts still match.
- `grade` — optional label (e.g. `Beginner`, `중3`). Difficulty is auto-computed from the graph.
- `questions` — optional curated quiz items. `answer` is the index of the correct choice. **Write correct keys!**

**2. Check it (no setup beyond `pip install -r requirements.txt`):**

```bash
.venv/bin/python - <<'PY'
import glob
from ingest.backbone import Backbone
BB = Backbone.from_jsons(sorted(glob.glob("data/backbone_*.json")))   # loads & validates all (errors on cycles / dup ids)
print("loaded", len(BB.concepts), "concepts")
print("pulled by your top concept:", BB.pulled_prereqs(["Chord Progressions"]))
PY
```

It auto-loads — no wiring, no registration. If it loads without error, **open your PR.** 🎉

> Tip: order matters more than completeness. A short, correctly-ordered chain
> (basic → advanced) beats a long, tangled one. Start small.

---

## 🟢 Add quiz questions to an existing subject

Find the concept in its `data/backbone_*.json` and add a `questions` entry:

```json
"questions": [
  {"stem": "Simplify 8/12.", "choices": ["2/3", "4/6", "8/12", "3/4"], "answer": 0}
]
```

These power the in-app **auto-graded** quiz. We use curated questions (not LLM-generated)
because trusted answer keys are what make the diagnosis reliable.

---

## Dev setup (for code changes)

```bash
git clone https://github.com/yuneunmi814-cmyk/pace-tutor.git && cd pace-tutor
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m sidecar.server      # backend  → :8008
cd ui && npm install && npm run dev      # frontend → :5173
```

Full details and the architecture diagram are in the [README](README.md).

## Before you open a PR

Run the deterministic checks (no LLM/network needed) — they should all pass:

```bash
.venv/bin/python verify_scenario.py
.venv/bin/python verify_backbone.py
.venv/bin/python verify_backbone_coding.py
.venv/bin/python verify_pull_prereqs.py
.venv/bin/python verify_questions.py
cd ui && npm run build        # type-check + build the UI
```

**Every PR is auto-checked** by CI (`.github/workflows/ci.yml`): it loads all backbones
(catching cycles, duplicate ids, and name collisions) and runs the deterministic suite +
UI build. So if the checks above pass locally, your PR will be green. ✅

If you changed extraction/structure quality, the `eval_*.py` scripts (need Ollama) show
the impact — include before/after numbers in your PR description; we love measurements. 📊

## Pull request guidelines

1. Branch off `main` (`feat/add-music-backbone`, `fix/quiz-key`, …).
2. Keep PRs focused — one subject / one fix per PR is easiest to review.
3. Describe **what** and **why**. For data PRs, a one-line "added Music backbone (EN), 6 concepts" is perfect.
4. Make sure the checks above pass.
5. Be kind in review — we're all here for the learners. 💛

**Commit style:** short imperative summary, e.g. `Add music theory backbone (EN)`.

## Project map

```
engine/    diagnosis + recommendation (numpy) — subject/language-agnostic
ingest/    any input → concept graph: loaders, STT, LLM extraction, structure, backbone
sidecar/   FastAPI server (:8008) wrapping engine + ingest
ui/        Vite + React desktop UI + Tauri shell
data/      curriculum backbones  ← most contributions land here
```

## Questions?

Open an issue with the **question** label — no question is too small. If you're an
educator and want to review/curate a subject's prerequisites, that's hugely welcome too.

---

## 한국어 요약

기여해 주셔서 감사합니다 🙌 전문가가 아니어도 됩니다. **가장 쉬운 첫 기여는 "과목 추가"** 예요 —
`data/backbone_<과목>_<언어>.json` 파일 하나에 개념과 선수관계만 적으면 됩니다(코드 불필요).

1. 위 [JSON 예시](#-your-first-pr-add-a-subject-just-one-json-file)처럼 파일을 만들고
2. `Backbone.from_jsons(...)`로 로드 에러만 없으면 (순환·중복 id 자동 검증)
3. PR 보내기 — 끝! 🎉

진단 엔진은 과목 무관이라 *어떤 주제든* 동작합니다. 필요한 건 신뢰할 수 있는 "무엇 먼저"
지도(백본)뿐이고, 로컬 LLM은 그걸 못 만듭니다(측정함). **당신이 아는 과목을 앱에 가르쳐 주세요.**

PR 전에 `verify_*.py`(LLM 불필요)와 `cd ui && npm run build`가 통과하는지만 확인해 주세요.
질문은 issue에 편하게 — 사소한 질문 환영합니다.
