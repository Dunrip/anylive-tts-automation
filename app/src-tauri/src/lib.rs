use std::sync::{Arc, Mutex};
use tauri::{
    menu::{Menu, MenuItem},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, WindowEvent,
};
use tauri_plugin_shell::ShellExt;

struct SidecarPort {
    port: Arc<Mutex<Option<u16>>>,
}

struct SidecarProcess {
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

#[tauri::command]
fn read_client_config(client: String) -> Result<String, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("configs"),
        cwd.join("../../configs"),
        cwd.join("../../../configs"),
        cwd.join("../../../../configs"),
    ];
    let configs_dir = candidates
        .iter()
        .find(|p| p.exists())
        .ok_or("Could not find configs directory")?
        .clone();
    let client_dir = configs_dir.join(&client);
    if !client_dir.exists() {
        return Err(format!("Config '{}' not found", client));
    }
    let mut result = String::from("{");
    let tts_path = client_dir.join("tts.json");
    if tts_path.exists() {
        let tts = std::fs::read_to_string(&tts_path).map_err(|e| e.to_string())?;
        result.push_str(&format!("\"tts\":{}", tts));
    }
    let live_path = client_dir.join("live.json");
    if live_path.exists() {
        if tts_path.exists() {
            result.push(',');
        }
        let live = std::fs::read_to_string(&live_path).map_err(|e| e.to_string())?;
        result.push_str(&format!("\"live\":{}", live));
    }
    result.push('}');
    Ok(result)
}

#[tauri::command]
fn save_client_config(client: String, tts: Option<String>, live: Option<String>) -> Result<(), String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("configs"),
        cwd.join("../../configs"),
        cwd.join("../../../configs"),
        cwd.join("../../../../configs"),
    ];
    let configs_dir = candidates
        .iter()
        .find(|p| p.exists())
        .ok_or("Could not find configs directory")?
        .clone();
    let client_dir = configs_dir.join(&client);
    if !client_dir.exists() {
        return Err(format!("Config '{}' not found", client));
    }
    if let Some(tts_json) = tts {
        std::fs::write(client_dir.join("tts.json"), tts_json).map_err(|e| e.to_string())?;
    }
    if let Some(live_json) = live {
        std::fs::write(client_dir.join("live.json"), live_json).map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn list_client_configs() -> Result<Vec<String>, String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("configs"),
        cwd.join("../../configs"),
        cwd.join("../../../configs"),
        cwd.join("../../../../configs"),
    ];
    let configs_dir = match candidates.iter().find(|p| p.exists()) {
        Some(p) => p.clone(),
        None => return Ok(vec!["default".to_string()]),
    };
    let mut clients: Vec<String> = std::fs::read_dir(&configs_dir)
        .map_err(|e| e.to_string())?
        .filter_map(|entry| {
            let entry = entry.ok()?;
            if entry.file_type().ok()?.is_dir() && !entry.file_name().to_str()?.starts_with('.') {
                Some(entry.file_name().to_str()?.to_string())
            } else {
                None
            }
        })
        .collect();
    clients.sort();
    if clients.is_empty() {
        clients.push("default".to_string());
    }
    Ok(clients)
}

#[tauri::command]
fn delete_client_config(name: String) -> Result<(), String> {
    if name == "default" {
        return Err("Cannot delete the default config".to_string());
    }
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("configs"),
        cwd.join("../../configs"),
        cwd.join("../../../configs"),
        cwd.join("../../../../configs"),
    ];
    let configs_dir = candidates
        .iter()
        .find(|p| p.exists())
        .ok_or("Could not find configs directory")?
        .clone();
    let target = configs_dir.join(&name);
    if !target.exists() {
        return Err(format!("Config '{}' not found", name));
    }
    std::fs::remove_dir_all(&target).map_err(|e| e.to_string())?;
    Ok(())
}

#[tauri::command]
fn create_client_config(name: String) -> Result<(), String> {
    let cwd = std::env::current_dir().map_err(|e| e.to_string())?;
    let candidates = [
        cwd.join("configs"),
        cwd.join("../../configs"),
        cwd.join("../../../configs"),
        cwd.join("../../../../configs"),
    ];
    let configs_dir = candidates
        .iter()
        .find(|p| p.exists())
        .ok_or_else(|| format!("Could not find configs directory (cwd: {})", cwd.display()))?
        .clone();
    let configs_dir = configs_dir.as_path();
    let default_dir = configs_dir.join("default");
    let new_dir = configs_dir.join(&name);
    if new_dir.exists() {
        return Err(format!("Config '{}' already exists", name));
    }
    if default_dir.exists() {
        fn copy_dir(src: &std::path::Path, dst: &std::path::Path) -> std::io::Result<()> {
            std::fs::create_dir_all(dst)?;
            for entry in std::fs::read_dir(src)? {
                let entry = entry?;
                let dest = dst.join(entry.file_name());
                if entry.file_type()?.is_dir() {
                    copy_dir(&entry.path(), &dest)?;
                } else {
                    std::fs::copy(entry.path(), dest)?;
                }
            }
            Ok(())
        }
        copy_dir(&default_dir, &new_dir).map_err(|e| e.to_string())?;
    } else {
        std::fs::create_dir_all(&new_dir).map_err(|e| e.to_string())?;
        std::fs::write(new_dir.join("tts.json"), "{}").map_err(|e| e.to_string())?;
        std::fs::write(new_dir.join("live.json"), "{}").map_err(|e| e.to_string())?;
    }
    Ok(())
}

#[tauri::command]
fn get_sidecar_port(state: tauri::State<SidecarPort>) -> Result<u16, String> {
    let guard = state.port.lock().map_err(|e| e.to_string())?;
    guard.ok_or_else(|| "Sidecar not ready yet".to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let sidecar_port = Arc::new(Mutex::new(None::<u16>));

    tauri::Builder::default()
        .manage(SidecarPort {
            port: sidecar_port.clone(),
        })
        .manage(SidecarProcess {
            child: Mutex::new(None),
        })
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            if let Some(window) = app.get_webview_window("main") {
                let _ = window.show();
                let _ = window.set_focus();
            }
        }))
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_notification::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_process::init())
        .setup(move |app| {
            #[cfg(desktop)]
            app.handle().plugin(tauri_plugin_updater::Builder::new().build())?;

            let is_dev = cfg!(debug_assertions);

            let (mut rx, child) = if is_dev {
                app.shell()
                    .command("python3")
                    .args(["../sidecar/server.py"])
                    .spawn()
                    .map_err(|e| format!("Failed to spawn sidecar: {e}"))?
            } else {
                {
                    let resource_dir = app
                        .path()
                        .resource_dir()
                        .map_err(|e| format!("Failed to get resource dir: {e}"))?;
                    let sidecar_name = if cfg!(target_os = "windows") {
                        "sidecar-server.exe"
                    } else {
                        "sidecar-server"
                    };
                    let sidecar_path = resource_dir.join("sidecar").join(sidecar_name);

                    app.shell()
                        .command(sidecar_path.to_string_lossy().to_string())
                        .spawn()
                        .map_err(|e| format!("Failed to spawn sidecar: {e}"))?
                }
            };

            {
                let state = app.state::<SidecarProcess>();
                let mut guard = state.child.lock().map_err(|e| e.to_string())?;
                *guard = Some(child);
            }

            let port_state = sidecar_port.clone();
            let app_handle = app.handle().clone();
            tauri::async_runtime::spawn(async move {
                use tauri_plugin_shell::process::CommandEvent;

                while let Some(event) = rx.recv().await {
                    match event {
                        CommandEvent::Stdout(bytes) => {
                            if let Ok(line) = String::from_utf8(bytes) {
                                let line = line.trim();
                                if let Some(port_str) = line.strip_prefix("SERVER_READY:") {
                                    if let Ok(port) = port_str.parse::<u16>() {
                                        if let Ok(mut guard) = port_state.lock() {
                                            *guard = Some(port);
                                        }
                                        if let Some(window) = app_handle.get_webview_window("main") {
                                            let _ = window.show();
                                            let _ = window.set_focus();
                                        }
                                        break;
                                    }
                                }
                            }
                        }
                        CommandEvent::Terminated(_) => break,
                        _ => {}
                    }
                }
            });

            let show_item = MenuItem::with_id(app, "show", "Show Window", true, None::<&str>)?;
            let quit_item = MenuItem::with_id(app, "quit", "Quit", true, None::<&str>)?;
            let menu = Menu::with_items(app, &[&show_item, &quit_item])?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .tooltip("AnyLive TTS")
                .on_tray_icon_event(|tray: &tauri::tray::TrayIcon, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .on_menu_event(|app: &tauri::AppHandle, event| match event.id.as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "quit" => {
                        let state = app.state::<SidecarProcess>();
                        if let Ok(mut guard) = state.child.lock() {
                            if let Some(mut child) = guard.take() {
                                let _ = child.write("shutdown\n".as_bytes());
                                std::thread::sleep(std::time::Duration::from_millis(500));
                                let _ = child.kill();
                            }
                        }
                        app.exit(0);
                    }
                    _ => {}
                })
                .build(app)?;

            if let Some(window) = app.get_webview_window("main") {
                let window_clone = window.clone();
                window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { api, .. } = event {
                        api.prevent_close();
                        let _ = window_clone.hide();
                    }
                });
            }

            Ok(())
        })
        .on_window_event(|window, event| {
            if matches!(event, WindowEvent::Destroyed) {
                let app = window.app_handle();
                let state = app.state::<SidecarProcess>();
                let child_lock = state.child.lock();
                if let Ok(mut guard) = child_lock {
                    if let Some(mut child) = guard.take() {
                        let _ = child.write("shutdown\n".as_bytes());
                        std::thread::sleep(std::time::Duration::from_millis(500));
                        let _ = child.kill();
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_port, list_client_configs, read_client_config, save_client_config, delete_client_config, create_client_config])
        .build(tauri::generate_context!())
        .expect("error while building tauri application")
        .run(|app_handle, event| {
            if let tauri::RunEvent::Exit = event {
                if let Ok(mut guard) = app_handle.state::<SidecarProcess>().child.lock() {
                    if let Some(mut child) = guard.take() {
                        let _ = child.write("shutdown\n".as_bytes());
                        std::thread::sleep(std::time::Duration::from_millis(500));
                        let _ = child.kill();
                    }
                }
            }
        });
}
