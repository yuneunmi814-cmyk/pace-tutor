# pace-tutor

**Learn at your own pace, not the world's — start from the basics.**

A desktop app that turns any lecture (video, audio, PDF, text, subtitles) into a
**personalized, self-paced learning path**. When a learner is stuck, it diagnoses
which concepts they've mastered and **traces back through prerequisites** to find
the deepest foundation they're actually ready to learn — instead of pushing them
through material they have no base for.

> Motivation: a 9th grader stuck on algebra often isn't failing algebra — they're
> missing an elementary fraction concept. pace-tutor finds that root gap and starts there.

Subject-agnostic (math, science, language, coding, …) and **English-first** with a
Korean toggle. Local-first: runs a bundled Python backend and talks to a local
[Ollama](https://ollama.com) model — no cloud required.

[한국어 README →](README.ko.md)

---

## How it works

```
video / audio / PDF / text / subtitles
        │  (loaders: faster-whisper STT, pypdf, …)
        ▼
     transcript text
        │  (Ollama, constrained decoding) → concepts
        │  + curriculum backbone → verified prerequisites (DAG)
        ▼
   concept graph  ──►  diagnosis engine  ──►  self-paced learning path
                        (Bayesian Knowledge      "start here now" + ordered steps,
                         Tracing + prerequisite   adapted to the learner's level band
                         back-tracking)           (elementary / secondary / adult)
```

Two algorithms do the heavy lifting (not the LLM):
- **Bayesian Knowledge Tracing** for per-concept mastery (`engine/`)
- **Prerequisite back-tracking** (ALOSI readiness/remediation scoring) for the path

**Everything is derived from the uploaded material**: concepts are extracted from the
transcript, and prerequisite *structure* is derived by asking the LLM to order the
extracted concepts from basic to advanced — a task it does reliably (measured ordering
accuracy ~1.0) unlike direct relation extraction (~0.33–0.5 F1). See `eval_structure.py`.

The **curriculum backbone is an optional overlay**, not a requirement. Its real job is
the one thing the material *can't* provide: the foundational prerequisites a lecture
assumes but never states. With `pull_prereqs` (on by default), a lecture that mentions
only "Quadratic Equations" pulls in fractions, GCD, etc. — so the learner can be checked
on them and routed all the way down to the real gap (the 9th-grader-missing-fractions
case). Backbones ship for **English and Korean** across **math, science, and programming**
(`data/backbone_*.json`, auto-merged); with `use_backbone` off, the app runs fully from
the material alone (no below-material foundations).

## Architecture

```
engine/      Diagnosis + recommendation (numpy). Subject- and language-agnostic.
ingest/      Any input → concept graph: loaders, STT, chunking, LLM extraction,
             curriculum backbone, DAG building.
sidecar/     FastAPI server (:8008) wrapping engine + ingest. Bundled into the app.
ui/          Vite + React + TS frontend (light theme, English-first i18n).
ui/src-tauri Tauri v2 desktop shell (Rust) — spawns the bundled sidecar.
data/        Curriculum backbone seed.
```

## Run (development)

```bash
# Backend
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m sidecar.server        # http://127.0.0.1:8008/docs

# Frontend (another terminal)
cd ui && npm install && npm run dev        # http://localhost:5173
```

Requires a running [Ollama](https://ollama.com) daemon for LLM extraction
(`ollama pull llama3.1:8b`) and `ffmpeg` for media. The "Try a sample instantly"
button works without any of that.

## Build the desktop app (macOS)

No Python needed by end users — the backend is bundled into the `.app`.

```bash
# 1) Install Rust (once): https://rustup.rs
# 2) Build the Python sidecar binary
.venv/bin/pip install pyinstaller
./scripts/build_sidecar.sh
# 3) Build the app
cd ui && npm install && npx tauri build
# → ui/src-tauri/target/release/bundle/{macos/pace-tutor.app, dmg/*.dmg}
```

Notes:
- The sidecar runs under hardened runtime, so `entitlements.plist` sets
  `com.apple.security.cs.disable-library-validation` (required for the bundled
  Python framework to load). The UI polls for the backend on first launch (~10s boot).
- For distribution to other Macs, add Apple notarization (currently adhoc-signed).

## Tests / verifications

```bash
.venv/bin/python verify_scenario.py      # diagnosis + back-tracking (math)
.venv/bin/python demo_multisubject.py    # subject-agnostic + level bands
.venv/bin/python verify_ingest.py        # transcript → graph
.venv/bin/python verify_loaders.py       # video/audio/PDF/text/subtitles → text
.venv/bin/python verify_backbone.py      # curriculum backbone — Korean (deterministic)
.venv/bin/python verify_backbone_en.py   # curriculum backbone — English (deterministic)
.venv/bin/python verify_backbone_coding.py # curriculum backbone — programming (EN+KO)
.venv/bin/python verify_pull_prereqs.py  # pull below-material foundations (the core motivation)
.venv/bin/python verify_sidecar.py       # sidecar HTTP API
.venv/bin/python verify_questions.py     # curated question bank (EN + KO, trusted keys)
.venv/bin/python eval_extraction.py      # LLM relation-extraction quality (weak)
.venv/bin/python eval_structure.py       # input-driven structure: ordering accuracy (strong)
```

## Status

Implemented & verified: diagnosis engine, ingest pipeline (all input types),
curriculum backbone, sidecar API, English-first UI, and a packaged macOS `.app`/`.dmg`
with the Python backend bundled (verified to launch and connect with no Python install).
Bundled **faster-whisper transcription is verified at runtime** (real audio → graph from
inside the `.app`). A **cross-platform release CI** (`.github/workflows/release.yml`)
builds macOS/Windows/Linux installers; macOS notarization runs from repo secrets — see
[docs/DISTRIBUTION.md](docs/DISTRIBUTION.md).

Diagnosis in the UI offers two reliable paths, both feeding the BKT engine:
- **Auto-graded quiz** from a curated question bank in the backbone (trusted answer
  keys) — used over LLM-generated quizzes because a local 8B model gets its own
  answers wrong (measured).
- **Graded self-assessment** (Know it / Unsure / No idea) for concepts without a
  curated quiz.

Roadmap: expand question bank & backbone (more subjects/languages), supply Apple
Developer secrets for notarized macOS releases, optional Windows/Linux code signing.

## Design references

Blueprints in this repo (Korean): `prerequisite-diagnosis-reference.md`,
`video-to-conceptgraph-reference.md`, `tauri-python-sidecar-reference.md`.
