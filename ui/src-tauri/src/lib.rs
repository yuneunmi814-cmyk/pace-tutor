// pace-tutor Tauri 셸 — Python 사이드카(:8008) spawn/모니터/종료.
// 출처: dieharders/example-tauri-v2-python-server-sidecar main.rs (v2 lib.rs 로 각색).
// ⚠️ 종료는 stdin "sidecar shutdown" — process.kill() 금지(PyInstaller 부트로더 PID 함정).

use std::sync::{Arc, Mutex};
use tauri::{Emitter, Manager, RunEvent};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;

fn spawn_sidecar(app: tauri::AppHandle) -> Result<(), String> {
    if let Some(state) = app.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        if state.lock().unwrap().is_some() {
            return Ok(()); // 이미 실행 중
        }
    }
    let cmd = app.shell().sidecar("main").map_err(|e| e.to_string())?;
    let (mut rx, child) = cmd.spawn().map_err(|e| e.to_string())?;
    if let Some(state) = app.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
        *state.lock().unwrap() = Some(child);
    }
    tauri::async_runtime::spawn(async move {
        while let Some(event) = rx.recv().await {
            match event {
                CommandEvent::Stdout(b) => {
                    let _ = app.emit("sidecar-stdout", String::from_utf8_lossy(&b).to_string());
                }
                CommandEvent::Stderr(b) => {
                    let _ = app.emit("sidecar-stderr", String::from_utf8_lossy(&b).to_string());
                }
                _ => {}
            }
        }
    });
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_http::init())
        .setup(|app| {
            if cfg!(debug_assertions) {
                app.handle().plugin(
                    tauri_plugin_log::Builder::default()
                        .level(log::LevelFilter::Info)
                        .build(),
                )?;
            }
            app.manage(Arc::new(Mutex::new(None::<CommandChild>)));
            if let Err(e) = spawn_sidecar(app.handle().clone()) {
                eprintln!("[tauri] sidecar spawn 실패: {e}");
            }
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while running tauri application")
        .run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                // 정상 종료 신호 (process.kill() 아님 — 부트로더 자식 프로세스까지 종료)
                if let Some(state) = app.try_state::<Arc<Mutex<Option<CommandChild>>>>() {
                    if let Ok(mut child) = state.lock() {
                        if let Some(p) = child.as_mut() {
                            let _ = p.write(b"sidecar shutdown\n");
                        }
                    }
                }
            }
        });
}
