use std::sync::{Arc, Mutex};

use serde_json::Value;
use tauri::State;
use tauri_plugin_shell::{process::CommandChild, process::CommandEvent, ShellExt};

struct SidecarPort {
    port: Arc<Mutex<Option<u16>>>,
}

struct SidecarProcess {
    _child: Arc<Mutex<Option<CommandChild>>>,
}

#[tauri::command]
async fn get_health(state: State<'_, SidecarPort>) -> Result<Value, String> {
    let port = {
        let guard = state.port.lock().map_err(|e| e.to_string())?;
        (*guard).ok_or_else(|| "Sidecar port not ready".to_string())?
    };

    let url = format!("http://127.0.0.1:{}/health", port);
    let response = reqwest::get(url).await.map_err(|e| e.to_string())?;
    if !response.status().is_success() {
        return Err(format!("Health check failed with status {}", response.status()));
    }
    response.json::<Value>().await.map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_port = Arc::new(Mutex::new(None));
    let sidecar_child = Arc::new(Mutex::new(None));

    tauri::Builder::default()
        .manage(SidecarPort {
            port: sidecar_port.clone(),
        })
        .manage(SidecarProcess {
            _child: sidecar_child.clone(),
        })
        .setup(move |app| {
            let sidecar_command = app.shell().sidecar("spike-server")?;
            let (mut rx, child) = sidecar_command.spawn()?;

            if let Ok(mut guard) = sidecar_child.lock() {
                *guard = Some(child);
            }

            let state = sidecar_port.clone();
            tauri::async_runtime::spawn(async move {
                while let Some(event) = rx.recv().await {
                    if let CommandEvent::Stdout(bytes) = event {
                        if let Ok(line) = String::from_utf8(bytes) {
                            if let Some(port_text) = line.trim().strip_prefix("SERVER_READY:") {
                                if let Ok(parsed_port) = port_text.parse::<u16>() {
                                    if let Ok(mut guard) = state.lock() {
                                        *guard = Some(parsed_port);
                                    }
                                    break;
                                }
                            }
                        }
                    }
                }
            });

            Ok(())
        })
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![get_health])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
