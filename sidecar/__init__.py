"""pace-tutor 사이드카 — engine + ingest 를 감싸는 HTTP API (FastAPI).

Tauri 데스크톱 앱이 이 사이드카를 PyInstaller 바이너리로 번들해 실행한다
(설계: tauri-python-sidecar-reference.md). 단, Tauri 없이도 HTTP로 단독 실행/테스트 가능.
"""
