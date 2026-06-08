# Tauri + Python 사이드카 번들링 — 구현 청사진 (reference)

> 목표: 이미 동작하는 Python 백엔드(`pace-tutor/engine` 진단엔진 + `pace-tutor/ingest`
> 영상→그래프 파이프라인)를 **PyInstaller로 바이너리화**해 **Tauri v2** 데스크톱 앱에
> 사이드카로 붙이고, **React(라이트테마) UI ↔ 사이드카**를 연결해
> "영상 드롭 → 진단 퀴즈 → 학습가이드/진도"를 보여준다.
>
> 이 문서는 **청사진**이다. 구현은 아직 하지 않는다.

---

## 0. 한 줄 결론

`dieharders/example-tauri-v2-python-server-sidecar`(⭐117, Apache-2.0, 2025-01)가
**정확히 우리 문제를 위한 목적특화 예제**다. 그 repo의 4개 핵심(PyInstaller 빌드 명령,
`externalBin` 설정, `capabilities` 권한, `main.rs` 생명주기)을 **거의 그대로 차용**하고,
우리만의 3가지를 추가/주의한다:

1. **Ollama는 사이드카에 넣지 않는다** — 별도 데몬(`localhost:11434`)으로 HTTP 호출. (사용자 이미 설치)
2. **faster-whisper(ctranslate2) PyInstaller 숨은 의존성** — `--collect-all` 필요. (최대 난제)
3. **ffmpeg** — faster-whisper가 영상 디코딩에 요구 → Tauri 리소스로 동봉하거나 시스템 의존.

> 참고: 사용자가 쓰는 **Meetily**도 Tauri+Python이지만, *별도 FastAPI 서버(5167) + whisper.cpp 서버(8178)*
> 를 따로 띄우는 방식이라 "원클릭 번들 사이드카" 정석은 아니다. 정석은 dieharders 예제다.

---

## 1. 레퍼런스 선정

| 후보 | 별점/상태 | 라이선스 | 채택? | 이유 |
|---|---|---|---|---|
| **dieharders/example-tauri-v2-python-server-sidecar** | ⭐117, 2025-01 | Apache-2.0 | ✅ **메인** | Tauri v2 + 프론트 + **PyInstaller FastAPI 사이드카** 목적특화. 생명주기(spawn/ready/shutdown)·target triple·권한까지 완비. |
| Meetily (Zackriya-Solutions/meeting-minutes) | 인기↑ | - | 참고만 | 사용자 사용 경험은 강점이나, 별도 서버 2개를 따로 실행하는 구조. 번들 사이드카 정석 아님. localhost 통신 패턴만 참고. |
| 공식 Tauri 문서 (v2 sidecar) | 공식 | - | ✅ 보조 | `externalBin`/capabilities/`Command.sidecar` 규약의 1차 출처. |
| pytauri (Python에서 Tauri 임베드) | 신생 | - | ❌ | 방향이 반대(파이썬이 호스트). 우리는 Rust 호스트 + 파이썬 사이드카가 맞음. |

---

## 2. 매핑표 — 레퍼런스 ↔ 우리 앱

| dieharders 예제 | 우리 대응 | 비고 |
|---|---|---|
| `src/backends/main.py` (FastAPI on :8008) | **`sidecar/server.py`** — engine+ingest를 감싼 FastAPI | 우리 함수 그대로 노출 |
| `inference/infer_text_api.py` (목 추론) | **engine.Recommender / ingest.pipeline 호출** | 이미 구현됨 |
| PyInstaller `-F` 단일 바이너리 | 동일 (+ faster-whisper `--collect-all`) | §3-A |
| `src-tauri/bin/api/main-<triple>` | 동일 경로/네이밍 | target triple 필수 |
| `tauri.conf.json: externalBin: ["bin/api/main"]` | 동일 | §3-B |
| `capabilities/migrated.json` sidecar 권한 | 동일 | §3-C |
| `main.rs` spawn+monitor+shutdown | **거의 그대로 복붙** | §3-D — 핵심 |
| stdin "sidecar shutdown\n" 종료 | 동일 (PyInstaller PID 함정) | §5-1 |
| Next.js 프론트 | **Vite + React (라이트테마)** | Next보다 가벼움. Next static export도 가능 |
| HTTP `:8008` API | **HTTP `:8008` API** + stdin 제어 | 통신은 HTTP, 종료만 stdin |
| (없음) | **Ollama HTTP `:11434`** | 사이드카가 Ollama로 호출 — 번들 안 함 §5-2 |
| (없음) | **ffmpeg 동봉/의존** | §5-3 |

호출할 우리 코드(이미 구현·검증됨):
- `engine`: `ConceptGraph`, `LearnerState`, `Recommender` (`verify_scenario.py`/`demo_multisubject.py` 통과)
- `ingest`: `transcript_to_graph`, `video_to_graph` (`verify_ingest.py` 통과)

---

## 3. 복붙용 코드/설정

### A. PyInstaller 빌드 (package.json scripts) — target triple 네이밍 필수

레퍼런스 `package.json` 그대로 + 우리 의존성(faster-whisper) 반영. **바이너리 이름은
`main-<TARGET_TRIPLE>` 형식이어야** Tauri가 사이드카로 인식한다.

```jsonc
// package.json  (출처: dieharders package.json, faster-whisper용 플래그 추가)
"scripts": {
  "build:sidecar-macos":  "pyinstaller -c -F --clean --name main-aarch64-apple-darwin       --distpath src-tauri/bin/api --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers sidecar/server.py",
  "build:sidecar-winos":  "pyinstaller -c -F --clean --name main-x86_64-pc-windows-msvc      --distpath src-tauri/bin/api --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers sidecar/server.py",
  "build:sidecar-linux":  "pyinstaller -c -F --clean --name main-x86_64-unknown-linux-gnu    --distpath src-tauri/bin/api --collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers sidecar/server.py"
}
```
> target triple 확인: `rustc -Vv | grep host`. Apple Silicon = `aarch64-apple-darwin`.
> numpy/ollama/pydantic은 보통 자동 수집되지만, 누락 에러 시 `--collect-all <pkg>` 추가.

### B. tauri.conf.json — externalBin (레퍼런스 그대로)

```jsonc
"bundle": {
  "active": true,
  "targets": "all",
  "externalBin": ["bin/api/main"],          // ← -<triple> 접미사는 Tauri가 자동 매칭
  "resources": ["resources/ffmpeg"],         // ← 우리 추가: ffmpeg 동봉 (§5-3)
  "macOS": { "signingIdentity": "-" }        // adhoc 서명 (개발/로컬)
}
```

### C. capabilities/default.json — 사이드카 실행 권한 (레퍼런스 각색)

```jsonc
{
  "identifier": "default",
  "windows": ["main"],
  "permissions": [
    "core:default",
    "core:window:default",
    {
      "identifier": "shell:allow-execute",
      "allow": [{ "args": false, "cmd": "", "name": "bin/api/main", "sidecar": true }]
    },
    "shell:default",
    "http:default"
  ]
}
```

### D. 🔑 src-tauri/src/main.rs — 사이드카 생명주기 (레퍼런스 거의 그대로)

핵심만 발췌(전체는 레퍼런스 `main.rs` 복붙). **종료는 반드시 stdin 명령** — `process.kill()` 금지(§5-1).

```rust
// 앱 시작 시 사이드카 spawn + stdout/stderr 모니터링
fn spawn_and_monitor_sidecar(app_handle: tauri::AppHandle) -> Result<(), String> {
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        if state.lock().unwrap().is_some() { return Ok(()); } // 중복 spawn 방지
    }
    let sidecar_command = app_handle.shell().sidecar("main").map_err(|e| e.to_string())?;
    let (mut rx, child) = sidecar_command.spawn().map_err(|e| e.to_string())?;
    if let Some(state) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        *state.lock().unwrap() = Some(child);
    }
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(b) => { let _ = app_handle.emit("sidecar-stdout", String::from_utf8_lossy(&b).to_string()); }
                CommandEvent::Stderr(b) => { let _ = app_handle.emit("sidecar-stderr", String::from_utf8_lossy(&b).to_string()); }
                _ => {}
            }
        }
    });
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            app.manage(Arc::new(Mutex::new(None::<CommandChild>)));
            spawn_and_monitor_sidecar(app.handle().clone()).ok();   // 시작 시 spawn
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![start_sidecar, shutdown_sidecar])
        .build(tauri::generate_context!()).expect("error")
        .run(|app_handle, event| if let RunEvent::ExitRequested { .. } = event {
            // 앱 종료 시: stdin 으로 정상 종료 신호 (process.kill() 아님!)
            if let Some(s) = app_handle.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
                if let Ok(mut child) = s.lock() {
                    if let Some(p) = child.as_mut() { let _ = p.write(b"sidecar shutdown\n"); }
                }
            }
        });
}
```
> Cargo.toml 의존성(레퍼런스): `tauri="2"`, `tauri-plugin-shell="2"`, `tauri-plugin-http="2"`, `serde`, `serde_json`.

### E. sidecar/server.py — 우리 백엔드 래퍼 (레퍼런스 main.py 골격 + 우리 함수)

```python
# sidecar/server.py  — 출처 골격: dieharders src/backends/main.py
import os, signal, sys, asyncio, threading
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from uvicorn import Config, Server

# 우리가 이미 만든 모듈 (PyInstaller가 함께 번들)
from engine import LearnerState, Recommender
from ingest.pipeline import transcript_to_graph, video_to_graph

PORT_API = 8008
app = FastAPI(title="pace-tutor sidecar", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- 앱이 쓰는 엔드포인트 (영상→그래프→진단→추천) ---
GRAPH = {"g": None}  # 데모용 메모리 상태 (운영은 SQLite)

@app.get("/v1/connect")
def connect():
    return {"port": PORT_API, "pid": os.getpid()}

@app.post("/v1/ingest")
def ingest(payload: dict = Body(...)):
    # {"video_path": "..."} 또는 {"transcript": "..."}
    if payload.get("video_path"):
        g = video_to_graph(payload["video_path"])
    else:
        g = transcript_to_graph(payload["transcript"])
    GRAPH["g"] = g
    return {"concepts": [{"id": c.id, "name": c.name, "prereqs": c.prereqs,
                          "difficulty": c.difficulty} for c in g.concepts]}

@app.post("/v1/recommend")
def recommend(payload: dict = Body(...)):
    g = GRAPH["g"]
    learner = LearnerState(g)
    for cid, responses in payload.get("responses", {}).items():
        learner.update_many(cid, responses)        # 진단 퀴즈 반영
    rec = Recommender(g, r_star=0.0, W_p=2.0)
    nxt = rec.next_concept(learner)
    return {"next": {"id": nxt.concept_id, "name": nxt.name, "mastery": nxt.mastery}}

# --- 종료 제어 (stdin) : PyInstaller PID 함정 회피 (§5-1) ---
def stdin_loop():
    for line in sys.stdin:
        if line.strip() == "sidecar shutdown":
            os.kill(os.getpid(), signal.SIGINT)

def main():
    t = threading.Thread(target=stdin_loop, daemon=True); t.start()
    asyncio.run(Server(Config(app, host="127.0.0.1", port=PORT_API, log_level="info")).serve())

if __name__ == "__main__":
    main()
```

### F. 프론트(React)에서 사이드카 호출

```ts
// HTTP로 사이드카 API 호출 (@tauri-apps/plugin-http)
import { fetch } from "@tauri-apps/plugin-http";
const res = await fetch("http://127.0.0.1:8008/v1/recommend", {
  method: "POST", headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ responses: { "gcd": [0,0,1] } }),
});
const { next } = await res.json();
```

---

## 4. 결정적 차이 — 우리가 더 단순/복잡해지는 지점

| 항목 | dieharders 예제 | 우리 | 그래서 |
|---|---|---|---|
| 백엔드 내용 | 목(mock) 추론 | **실제 engine+ingest (검증됨)** | server.py는 얇은 래퍼만 — 단순 |
| LLM | 없음 | **Ollama 별도 데몬(HTTP)** | 사이드카에 LLM 미포함 → 바이너리 가벼움. 단 Ollama 설치 전제 §5-2 |
| STT | 없음 | **faster-whisper 번들** | PyInstaller `--collect-all` 필요 — 복잡 §5-4 |
| 미디어 | 없음 | **ffmpeg 필요** | 리소스 동봉 또는 시스템 의존 §5-3 |
| 프론트 | Next.js | **Vite+React 라이트테마** | Next 정적 export 군더더기 제거 → 단순 |
| 통신 | HTTP + stdin | 동일 | 그대로 |
| 바이너리 크기 | 작음 | **큼(ctranslate2+모델)** | 첫 실행 시 whisper 모델 다운로드 고려 §5-5 |

---

## 5. 함정(gotcha) — 레퍼런스 소스에서 직접 확인 + 우리 의존성 분석

1. **`process.kill()` 금지 (PyInstaller `-F` 부트로더)**: 레퍼런스 `main.rs` 주석에 명시 —
   *"Tauri only knows the pid of the PyInstaller bootloader process and not its child process."*
   one-file 빌드는 부트로더가 진짜 파이썬 프로세스를 자식으로 띄우므로, `process.kill()`은
   부모만 죽이고 서버는 좀비로 남는다. → **stdin `"sidecar shutdown\n"` → 파이썬이 `SIGINT`로 자결**(§3-D,E).
   (one-file이 아니라 one-dir 빌드면 `process.kill()` 가능하나, 배포가 번거로움.)

2. **Ollama는 번들하지 않는다**: Ollama는 별도 데몬. 사이드카는 `http://localhost:11434`로 호출만 한다.
   → 앱 시작 시 **Ollama 실행 여부를 확인**하고, 없으면 사용자에게 안내(설치/`ollama serve`)하는 UX 필요.
   사용자는 이미 설치(llama3.1:8b 보유)했지만 배포 대상은 그렇지 않을 수 있음.

3. **ffmpeg 의존**: faster-whisper는 wav 외 포맷(mp4 등)을 ffmpeg로 디코딩. 두 선택:
   (a) `resources/ffmpeg` 바이너리를 동봉하고 사이드카에서 `imageio-ffmpeg` 또는 경로 지정,
   (b) 시스템 ffmpeg 의존(사용자 설치). 데스크톱 배포라면 (a) 권장. macOS는 서명/공증 시 동봉 바이너리도 서명 대상.

4. **faster-whisper PyInstaller 숨은 의존성**: `ctranslate2`(네이티브 .dylib/.so/.dll),
   `tokenizers`(Rust 확장), `onnxruntime`(VAD 사용 시)이 자동 수집 안 될 수 있음.
   → `--collect-all faster_whisper --collect-all ctranslate2 --collect-all tokenizers` (필요시 onnxruntime 추가).
   빌드 후 **반드시 실제 영상으로 1회 실행 테스트** — import는 되는데 런타임에 .dylib 못 찾는 케이스 흔함.

5. **Whisper 모델 다운로드 시점**: faster-whisper는 첫 사용 시 모델을 HF 캐시에 받는다(수백MB~).
   PyInstaller 바이너리에 모델을 안 넣으면 **첫 실행에 네트워크 필요**. → 모델을 리소스로 동봉하거나,
   최초 실행 시 다운로드 진행률 UI 제공. 데스크톱 기본은 `base`/`small`+`int8`로 크기 억제.

6. **CORS / 포트 충돌**: 레퍼런스는 `allow_origins=["*"]`(개발용). 사이드카는 `127.0.0.1`에만 바인딩하고
   (외부 노출 차단), 포트(8008) 충돌 대비 사용 가능 포트 탐색 로직 권장.

7. **사이드카 ready 대기**: spawn 직후 서버가 바로 안 뜬다. 프론트는 `/v1/connect`를
   **폴링/재시도**로 기다려야 함(레퍼런스도 readiness를 IPC로 신호). 첫 요청을 바로 쏘면 실패.

8. **macOS 공증(notarization)**: 외부 배포 시 동봉 바이너리(사이드카·ffmpeg·.dylib)까지 서명·공증 필요.
   로컬/개발은 `signingIdentity: "-"`(adhoc)로 충분하나 배포는 별도 작업.

---

## 6. 실행 순서 체크리스트

- [ ] Tauri v2 프로젝트 초기화: `pnpm create tauri-app` (프론트 = React/Vite, 라이트테마 CSS)
- [ ] `sidecar/server.py` 작성: engine+ingest 래핑 FastAPI(:8008) + stdin 종료 루프 (§3-E)
- [ ] `requirements.txt`에 `fastapi`, `uvicorn[standard]`, `pyinstaller` 추가 (+ 기존 numpy/ollama/pydantic/faster-whisper)
- [ ] target triple 확인(`rustc -Vv`) → `package.json` 빌드 스크립트의 `main-<triple>` 이름 맞춤 (§3-A)
- [ ] PyInstaller 빌드: `pnpm build:sidecar-macos` → `src-tauri/bin/api/main-aarch64-apple-darwin` 생성 확인
- [ ] **바이너리 단독 실행 테스트**: `./src-tauri/bin/api/main-<triple>` → `:8008/docs` 열리는지, 실제 영상 ingest 되는지(ffmpeg/whisper .dylib 로딩) §5-4
- [ ] `tauri.conf.json` externalBin + resources(ffmpeg) (§3-B), `capabilities/default.json` 사이드카 권한 (§3-C)
- [ ] `src-tauri/src/main.rs` 생명주기 복붙 (§3-D), Cargo.toml 플러그인 추가
- [ ] 프론트: Ollama 데몬 체크 → 영상 드롭 → `/v1/ingest` → 진단 퀴즈 → `/v1/recommend` → 학습가이드 표시
- [ ] `/v1/connect` 폴링으로 사이드카 ready 대기 (§5-7)
- [ ] `pnpm tauri dev`로 통합 실행 → `pnpm tauri build`로 .dmg/.exe 생성
- [ ] 종료 동작 확인: 창 닫을 때 파이썬 프로세스가 좀비로 안 남는지 (`ps` 확인) §5-1
- [ ] (배포 시) macOS 공증/서명, Whisper 모델 동봉 또는 최초 다운로드 UX §5-5,8

---

## 7. 참고한 레퍼런스 실제 파일

- `dieharders/example-tauri-v2-python-server-sidecar` (⭐117, Apache-2.0, 2025-01)
  - `package.json` — PyInstaller `-F` 빌드 스크립트 3종(target triple 네이밍)
  - `src-tauri/tauri.conf.json` — `externalBin: ["bin/api/main"]`, macOS adhoc 서명
  - `src-tauri/capabilities/migrated.json` — `shell:allow-execute` + `sidecar:true`
  - `src-tauri/src/main.rs` — spawn/monitor/shutdown 생명주기, **`process.kill()` 금지 주석**(PyInstaller PID 함정)
  - `src/backends/main.py` — FastAPI(:8008) + `stdin_loop`/`kill_process`(stdin 종료) + CORS
  - `src-tauri/Cargo.toml` — `tauri-plugin-shell`/`tauri-plugin-http` v2
- Tauri 공식 v2 문서 — `Embedding External Binaries`(externalBin, `-$TARGET_TRIPLE`, `Command.sidecar`), `Capabilities`/`Permissions`
- (참고) Meetily `meeting-minutes` — 별도 FastAPI(5167)+whisper.cpp(8178) 서버 패턴(번들 사이드카 아님)
