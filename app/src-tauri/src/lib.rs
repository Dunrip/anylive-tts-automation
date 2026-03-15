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
        .plugin(tauri_plugin_shell::init())
        .setup(move |app| {
            let sidecar_command = app.shell().command("python3").args(["app/sidecar/server.py"]);

            let (mut rx, child) = sidecar_command
                .spawn()
                .map_err(|e| format!("Failed to spawn sidecar: {e}"))?;

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
                    }
                }
            }
        })
        .invoke_handler(tauri::generate_handler![get_sidecar_port])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
