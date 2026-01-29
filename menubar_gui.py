#!/usr/bin/env python3
"""
AnyLive TTS Automation - Menu Bar Application
macOS menu bar application using rumps for team-friendly TTS automation.
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import queue
from pathlib import Path
from typing import Optional, Callable

import rumps

# Import from auto_tts
from auto_tts import run_job, setup_login, set_app_support_dir, is_session_valid

# App Support directory (macOS standard)
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "AnyLiveTTS"
CONFIGS_DIR = APP_SUPPORT_DIR / "configs"
LOGS_DIR = APP_SUPPORT_DIR / "logs"
SCREENSHOTS_DIR = APP_SUPPORT_DIR / "screenshots"
SESSION_FILE_PATH = APP_SUPPORT_DIR / "session_state.json"
STATE_FILE_PATH = APP_SUPPORT_DIR / "menubar_state.json"

# UI thread helper: background threads should not call rumps UI functions directly.
_UI_QUEUE: "queue.Queue[Callable[[], None]]" = queue.Queue()


def ui_call(fn: Callable[[], None]) -> None:
    """Schedule a UI update/notification to run on the main rumps thread."""
    _UI_QUEUE.put(fn)


def setup_app_support():
    """Create App Support directory structure and copy default configs."""
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    CONFIGS_DIR.mkdir(exist_ok=True)
    LOGS_DIR.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    (APP_SUPPORT_DIR / "browser_data").mkdir(exist_ok=True)
    
    # Copy bundled configs if they don't exist
    bundled_configs = Path(__file__).parent / "configs"
    for config_file in ["default.json", "template.json"]:
        bundled = bundled_configs / config_file
        target = CONFIGS_DIR / config_file
        if bundled.exists() and not target.exists():
            shutil.copy(bundled, target)
    
    # Set app support dir for auto_tts module
    set_app_support_dir(str(APP_SUPPORT_DIR))


def check_chromium_installed() -> bool:
    """Check if Playwright Chromium is installed.

    IMPORTANT: Don't launch Chromium as a health check.
    In some macOS contexts (screen sharing, background sessions, CI-like shells),
    Chromium can crash at launch with SIGTRAP/NotificationCenter errors even though
    it is correctly installed. For the menubar app we only need to know whether the
    browser artifacts are present.
    """
    try:
        cache_dir = Path.home() / "Library" / "Caches" / "ms-playwright"
        if not cache_dir.exists():
            return False

        # Any installed chromium build directory counts.
        candidates = list(cache_dir.glob("chromium-*")) + list(cache_dir.glob("chromium_headless_shell-*"))
        return any(p.exists() for p in candidates)
    except Exception:
        return False


def install_chromium(callback=None):
    """Install Playwright Chromium browser."""
    try:
        if callback:
            callback("Installing Chromium browser... This may take a few minutes.")
        
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        if result.returncode == 0:
            if callback:
                callback("Chromium installed successfully!")
            return True
        else:
            if callback:
                callback(f"Installation failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        if callback:
            callback("Installation timed out. Please check your internet connection.")
        return False
    except Exception as e:
        if callback:
            callback(f"Installation error: {e}")
        return False


def list_configs() -> list:
    """List available config files in App Support."""
    if not CONFIGS_DIR.exists():
        return []
    configs = [f.stem for f in CONFIGS_DIR.glob("*.json") if f.stem != "template"]
    return sorted(configs)


def validate_csv(csv_path: str) -> dict:
    """Validate CSV and return summary info."""
    try:
        import pandas as pd
        
        # Try UTF-8 first, then CP874
        try:
            df = pd.read_csv(csv_path, encoding="utf-8", header=0)
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="cp874", header=0)
        
        # Detect columns
        expected_cols = ["No", "Product Name", "TH Script", "Audio Code"]
        found_cols = [col for col in expected_cols if col in df.columns]
        missing_cols = [col for col in expected_cols if col not in df.columns]
        
        # Count rows with data
        valid_rows = len(df[df["TH Script"].notna() | df["Audio Code"].notna()]) if "TH Script" in df.columns and "Audio Code" in df.columns else len(df)
        
        # Detect unique products
        products = []
        if "Product Name" in df.columns:
            df["Product Name"] = df["Product Name"].ffill()
            products = df["Product Name"].dropna().unique().tolist()
        
        return {
            "success": True,
            "rows": len(df),
            "valid_rows": valid_rows,
            "columns_found": found_cols,
            "columns_missing": missing_cols,
            "products": len(products),
            "product_names": products[:5]
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def select_file_dialog():
    """Show native macOS file picker using AppleScript."""
    script = '''
    tell application "System Events"
        activate
        set theFile to choose file with prompt "Select CSV file" of type {"csv", "public.comma-separated-values-text"}
        return POSIX path of theFile
    end tell
    '''
    try:
        result = subprocess.run(['osascript', '-e', script], capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception:
        return None


class AnyLiveTTSApp(rumps.App):
    """Main menu bar application."""
    
    def __init__(self):
        super(AnyLiveTTSApp, self).__init__("🎙️ TTS", quit_button=None)
        
        # State variables
        self.selected_config = None
        self.csv_path = None
        self.options = {
            # macOS app default: show the browser (headless = False)
            'headless': False,
            'dry_run': False,
            'no_save': False,
            'debug': False,
            'start_version': None,
            'limit': None
        }
        self.running = False
        self.chromium_installed = False
        self.session_valid = False
        self.job_thread = None
        
        # Setup app support
        setup_app_support()
        
        # Load persisted state
        self.load_state()
        
        # Check initial status
        self.chromium_installed = check_chromium_installed()
        self.session_valid = is_session_valid()
        
        # Build menu
        self.build_menu()
        
        # UI queue pump (runs on main thread)
        self._ui_timer = rumps.Timer(self._drain_ui_queue, 0.25)
        self._ui_timer.start()

        # Update menu status
        self.update_menu_status()
    
    def _drain_ui_queue(self, _sender=None):
        """Run pending UI tasks from background threads."""
        # Avoid starving the event loop; process a small batch per tick.
        for _ in range(25):
            try:
                fn = _UI_QUEUE.get_nowait()
            except queue.Empty:
                return
            try:
                fn()
            except Exception:
                # Never let UI queue processing crash the app.
                logging.exception("UI task failed")

    def build_menu(self):
        """Build the complete menu structure."""
        # Status section
        self.menu_chromium_status = rumps.MenuItem("Chromium: Checking...")
        self.menu_session_status = rumps.MenuItem("Session: Checking...")
        self.menu_config_status = rumps.MenuItem("Config: None")
        self.menu_csv_status = rumps.MenuItem("CSV: None")
        
        self.menu.add(self.menu_chromium_status)
        self.menu.add(self.menu_session_status)
        self.menu.add(self.menu_config_status)
        self.menu.add(self.menu_csv_status)
        self.menu.add(rumps.separator)
        
        # Config menu
        self.menu_config = rumps.MenuItem("📁 Config")
        self.menu.add(self.menu_config)
        self.rebuild_config_menu()
        
        # CSV menu
        self.menu_csv = rumps.MenuItem("📄 CSV")
        self.menu_csv.add(rumps.MenuItem("Select CSV File...", callback=self.select_csv))
        self.menu_csv.add(rumps.MenuItem("Validate CSV", callback=self.validate_csv_action))
        self.menu_csv.add(rumps.MenuItem("Clear CSV", callback=self.clear_csv))
        self.menu.add(self.menu_csv)
        
        # Options menu
        self.menu_options = rumps.MenuItem("⚙️ Options")
        self.menu_visible = rumps.MenuItem("Browser Visible", callback=self.toggle_visible)
        self.menu_dry_run = rumps.MenuItem("Dry Run", callback=self.toggle_dry_run)
        self.menu_no_save = rumps.MenuItem("No Save", callback=self.toggle_no_save)
        self.menu_debug = rumps.MenuItem("Debug Mode", callback=self.toggle_debug)
        
        self.menu_visible.state = not self.options['headless']
        self.menu_options.add(self.menu_visible)
        self.menu_options.add(self.menu_dry_run)
        self.menu_options.add(self.menu_no_save)
        self.menu_options.add(self.menu_debug)
        self.menu_options.add(rumps.separator)
        self.menu_options.add(rumps.MenuItem("Set Start Version...", callback=self.set_start_version))
        self.menu_options.add(rumps.MenuItem("Set Limit...", callback=self.set_limit))
        self.menu.add(self.menu_options)
        
        self.menu.add(rumps.separator)
        
        # Actions
        self.menu_install_chromium = rumps.MenuItem("Install Chromium", callback=self.install_chromium_action)
        self.menu_test = rumps.MenuItem("🧪 Test", callback=self.test_action)
        self.menu_setup_login = rumps.MenuItem("Setup Login", callback=self.setup_login_action)
        self.menu_run_automation = rumps.MenuItem("▶️ Run Automation", callback=self.run_automation_action)
        self.menu_stop_automation = rumps.MenuItem("⏹ Stop Automation", callback=self.stop_automation_action)
        self.menu_diagnostics = rumps.MenuItem("🩺 Diagnostics", callback=self.diagnostics_action)

        self.menu.add(self.menu_install_chromium)
        self.menu.add(self.menu_test)
        self.menu.add(self.menu_setup_login)
        self.menu.add(self.menu_run_automation)
        self.menu.add(self.menu_stop_automation)
        self.menu.add(self.menu_diagnostics)
        
        self.menu.add(rumps.separator)
        
        # Folders
        self.menu_folders = rumps.MenuItem("📂 Folders")
        self.menu_folders.add(rumps.MenuItem("Open Logs", callback=self.open_logs_folder))
        self.menu_folders.add(rumps.MenuItem("Open Screenshots", callback=self.open_screenshots_folder))
        self.menu_folders.add(rumps.MenuItem("Open Configs", callback=self.open_configs_folder))
        self.menu.add(self.menu_folders)
        
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=self.quit_app))
    
    def rebuild_config_menu(self):
        """Rebuild config submenu with current configs."""
        # Clear existing items if menu exists
        try:
            self.menu_config.clear()
        except AttributeError:
            pass
        
        configs = list_configs()
        if configs:
            for config in configs:
                self.menu_config.add(rumps.MenuItem(config, callback=self.select_config))
        else:
            self.menu_config.add(rumps.MenuItem("No configs found", callback=None))
        
        self.menu_config.add(rumps.separator)
        self.menu_config.add(rumps.MenuItem("Edit Config...", callback=self.edit_config))
        self.menu_config.add(rumps.MenuItem("New Config...", callback=self.new_config))
        self.menu_config.add(rumps.MenuItem("Refresh Configs", callback=self.refresh_configs))
    
    def update_menu_status(self):
        """Update status menu items."""
        # Chromium status
        if self.chromium_installed:
            self.menu_chromium_status.title = "Chromium: ✅ Installed"
        else:
            self.menu_chromium_status.title = "Chromium: ❌ Not Installed"
        
        # Session status
        if self.session_valid:
            self.menu_session_status.title = "Session: ✅ Valid"
        else:
            self.menu_session_status.title = "Session: ❌ Invalid"
        
        # Config status
        if self.selected_config:
            self.menu_config_status.title = f"Config: {self.selected_config}"
        else:
            self.menu_config_status.title = "Config: None"
        
        # CSV status
        if self.csv_path:
            csv_name = Path(self.csv_path).name
            self.menu_csv_status.title = f"CSV: {csv_name}"
        else:
            self.menu_csv_status.title = "CSV: None"
        
        # Update option checkboxes
        self.menu_visible.state = not self.options['headless']
        self.menu_dry_run.state = self.options['dry_run']
        self.menu_no_save.state = self.options['no_save']
        self.menu_debug.state = self.options['debug']
        
        # Keep callbacks always enabled so clicks never "do nothing".
        # When prerequisites are missing, handlers will explain what's needed.
        self.menu_install_chromium.set_callback(self.install_chromium_action)
        self.menu_run_automation.set_callback(self.run_automation_action)
        self.menu_stop_automation.set_callback(self.stop_automation_action)

        # Reflect availability via title/state only.
        self.menu_install_chromium.title = (
            "Install Chromium" if not self.chromium_installed else "Install Chromium (Already Installed)"
        )
        self.menu_run_automation.title = (
            "▶️ Run Automation" if not self.running else "▶️ Run Automation (Running...)"
        )
        self.menu_stop_automation.title = (
            "⏹ Stop Automation" if self.running else "⏹ Stop Automation"
        )
    
    def save_state(self):
        """Save current state to JSON file."""
        try:
            state = {
                'selected_config': self.selected_config,
                'csv_path': self.csv_path,
                'options': self.options
            }
            with open(STATE_FILE_PATH, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Failed to save state: {e}")
    
    def load_state(self):
        """Load state from JSON file."""
        try:
            if STATE_FILE_PATH.exists():
                with open(STATE_FILE_PATH, 'r') as f:
                    state = json.load(f)
                self.selected_config = state.get('selected_config')
                self.csv_path = state.get('csv_path')
                self.options.update(state.get('options', {}))
        except Exception as e:
            print(f"Failed to load state: {e}")

        # Default config: if nothing selected yet, use configs/default.json.
        # (The app copies bundled configs into App Support on first run.)
        if not self.selected_config:
            default_path = CONFIGS_DIR / "default.json"
            if default_path.exists():
                self.selected_config = "default"
    
    def select_config(self, sender):
        """Select a config from the menu."""
        self.selected_config = sender.title
        self.save_state()
        self.update_menu_status()
        rumps.notification("Config Selected", "", f"Using config: {self.selected_config}")
    
    def edit_config(self, sender):
        """Open selected config in default text editor."""
        if not self.selected_config:
            rumps.alert("No Config Selected", "Please select a config first.")
            return
        
        config_path = CONFIGS_DIR / f"{self.selected_config}.json"
        if config_path.exists():
            subprocess.call(['open', str(config_path)])
        else:
            rumps.alert("Config Not Found", f"Config file not found: {config_path}")
    
    def new_config(self, sender):
        """Create a new config from template."""
        response = rumps.Window(
            title="New Config",
            message="Enter new config name:",
            default_text="my_config",
            ok="Create",
            cancel="Cancel"
        ).run()
        
        if response.clicked:
            config_name = response.text.strip()
            if not config_name:
                rumps.alert("Invalid Name", "Config name cannot be empty.")
                return
            
            template_path = CONFIGS_DIR / "template.json"
            new_config_path = CONFIGS_DIR / f"{config_name}.json"
            
            if new_config_path.exists():
                rumps.alert("Config Exists", f"Config '{config_name}' already exists.")
                return
            
            if not template_path.exists():
                rumps.alert("Template Not Found", "Template config not found.")
                return
            
            try:
                shutil.copy(template_path, new_config_path)
                self.rebuild_config_menu()
                subprocess.call(['open', str(new_config_path)])
                rumps.notification("Config Created", "", f"Created config: {config_name}")
            except Exception as e:
                rumps.alert("Error", f"Failed to create config: {e}")
    
    def refresh_configs(self, sender):
        """Refresh the config list."""
        self.rebuild_config_menu()
        rumps.notification("Configs Refreshed", "", "Config list updated")
    
    def select_csv(self, sender):
        """Select a CSV file."""
        csv_path = select_file_dialog()
        
        if not csv_path:
            response = rumps.Window(
                title="Select CSV File",
                message="Enter full path to CSV file:",
                default_text="",
                ok="Select",
                cancel="Cancel"
            ).run()
            
            if response.clicked:
                csv_path = response.text.strip()
        
        if csv_path and Path(csv_path).exists():
            self.csv_path = csv_path
            self.save_state()
            self.update_menu_status()
            rumps.notification("CSV Selected", "", f"Using: {Path(csv_path).name}")
        elif csv_path:
            rumps.alert("File Not Found", f"CSV file not found: {csv_path}")
    
    def validate_csv_action(self, sender):
        """Validate the selected CSV file."""
        if not self.csv_path:
            rumps.alert("No CSV Selected", "Please select a CSV file first.")
            return
        
        result = validate_csv(self.csv_path)
        
        if result['success']:
            message = (
                f"Rows: {result['rows']}\n"
                f"Valid rows: {result['valid_rows']}\n"
                f"Products: {result['products']}\n"
                f"Columns found: {', '.join(result['columns_found'])}\n"
            )
            if result['columns_missing']:
                message += f"Missing: {', '.join(result['columns_missing'])}"
            rumps.alert("CSV Valid", message)
        else:
            rumps.alert("CSV Invalid", f"Error: {result['error']}")
    
    def clear_csv(self, sender):
        """Clear the selected CSV file."""
        self.csv_path = None
        self.save_state()
        self.update_menu_status()
        rumps.notification("CSV Cleared", "", "CSV selection cleared")
    
    def toggle_visible(self, sender):
        """Toggle browser visible mode."""
        self.options['headless'] = not sender.state
        self.save_state()
        self.update_menu_status()
    
    def toggle_dry_run(self, sender):
        """Toggle dry run mode."""
        self.options['dry_run'] = not sender.state
        self.save_state()
        self.update_menu_status()
    
    def toggle_no_save(self, sender):
        """Toggle no save mode."""
        self.options['no_save'] = not sender.state
        self.save_state()
        self.update_menu_status()
    
    def toggle_debug(self, sender):
        """Toggle debug mode."""
        self.options['debug'] = not sender.state
        self.save_state()
        self.update_menu_status()
    
    def set_start_version(self, sender):
        """Set start version number."""
        response = rumps.Window(
            title="Set Start Version",
            message="Enter start version number (leave empty for none):",
            default_text=str(self.options['start_version']) if self.options['start_version'] else "",
            ok="Set",
            cancel="Cancel"
        ).run()
        
        if response.clicked:
            text = response.text.strip()
            if text:
                try:
                    version = int(text)
                    self.options['start_version'] = version
                    self.save_state()
                    rumps.notification("Start Version Set", "", f"Start version: {version}")
                except ValueError:
                    rumps.alert("Invalid Input", "Please enter a valid integer.")
            else:
                self.options['start_version'] = None
                self.save_state()
                rumps.notification("Start Version Cleared", "", "Start version reset")
    
    def set_limit(self, sender):
        """Set version limit."""
        response = rumps.Window(
            title="Set Version Limit",
            message="Enter number of versions to process (leave empty for all):",
            default_text=str(self.options['limit']) if self.options['limit'] else "",
            ok="Set",
            cancel="Cancel"
        ).run()
        
        if response.clicked:
            text = response.text.strip()
            if text:
                try:
                    limit = int(text)
                    self.options['limit'] = limit
                    self.save_state()
                    rumps.notification("Limit Set", "", f"Processing limit: {limit}")
                except ValueError:
                    rumps.alert("Invalid Input", "Please enter a valid integer.")
            else:
                self.options['limit'] = None
                self.save_state()
                rumps.notification("Limit Cleared", "", "Processing all versions")
    
    def install_chromium_action(self, sender):
        """Install Chromium browser."""
        if self.chromium_installed:
            rumps.alert("Chromium", "Chromium is already installed.")
            return

        def install_thread():
            ui_call(lambda: rumps.notification("Installing Chromium", "", "This may take a few minutes..."))
            success = install_chromium()
            if success:
                self.chromium_installed = True
                ui_call(self.update_menu_status)
                ui_call(lambda: rumps.notification("Installation Complete", "", "Chromium installed successfully"))
            else:
                ui_call(lambda: rumps.notification("Installation Failed", "", "Please check your internet connection"))

        threading.Thread(target=install_thread, daemon=True).start()
    
    def setup_login_action(self, sender):
        """Setup login session."""
        def setup_thread():
            logger = logging.getLogger(__name__)
            try:
                logger.info("🔐 Setup Login button clicked - starting setup process")

                # Let the UI thread show notifications.
                ui_call(lambda: rumps.notification(
                    "Setup Login",
                    "",
                    "Browser will open. Please log in in the browser window."
                ))

                asyncio.run(setup_login(logger, gui_mode=True))
                self.session_valid = is_session_valid()
                ui_call(self.update_menu_status)
                ui_call(lambda: rumps.notification("Login Complete", "", "Session saved successfully"))
            except Exception as e:
                logger.exception("❌ Setup Login failed")
                ui_call(lambda: rumps.notification("Login Failed", "", f"Error: {e}"))
        
        threading.Thread(target=setup_thread, daemon=True).start()
    
    def _prereq_report(self) -> str:
        missing = []
        if not self.selected_config:
            missing.append("Config not selected")
        if not self.csv_path:
            missing.append("CSV not selected")
        if not self.chromium_installed:
            missing.append("Chromium not installed")
        if not self.session_valid:
            missing.append("Session not valid (run Setup Login)")
        if self.running:
            missing.append("Automation already running")

        details = [
            f"Chromium installed: {self.chromium_installed}",
            f"Session valid: {self.session_valid}",
            f"Selected config: {self.selected_config or 'None'}",
            f"CSV: {Path(self.csv_path).name if self.csv_path else 'None'}",
            f"Browser visible: {not self.options['headless']}",
            f"Dry run: {self.options['dry_run']}",
            f"No save: {self.options['no_save']}",
            f"Debug: {self.options['debug']}",
        ]

        if missing:
            return "NOT READY\n\nMissing:\n- " + "\n- ".join(missing) + "\n\n" + "\n".join(details)
        return "READY\n\n" + "\n".join(details)

    def diagnostics_action(self, sender):
        """Show a quick status report so users understand why buttons may be blocked."""
        rumps.alert("Diagnostics", self._prereq_report())

    def test_action(self, sender):
        """Test action to verify app is working."""
        rumps.alert("Test", "App is working! Button clicked successfully.")
    
    def run_automation_action(self, sender):
        """Run the automation."""
        # Always explain why we can't run, instead of silently disabling the menu item.
        if self.running:
            rumps.alert("Already Running", "Automation is already running. Use 'Stop Automation' first.")
            return

        if not self.selected_config or not self.csv_path or not self.chromium_installed or not self.session_valid:
            rumps.alert("Not Ready", self._prereq_report())
            return

        self.running = True
        self.update_menu_status()
        
        def run_thread():
            try:
                ui_call(lambda: rumps.notification(
                    "Automation Started", "", f"Processing {Path(self.csv_path).name}"
                ))

                # Run job
                asyncio.run(run_job(
                    client_config=self.selected_config,
                    csv_file=self.csv_path,
                    headless=self.options['headless'],
                    dry_run=self.options['dry_run'],
                    no_save=self.options['no_save'],
                    debug_mode=self.options['debug'],
                    start_version=self.options['start_version'],
                    limit=self.options['limit'],
                    log_callback=None
                ))

                ui_call(lambda: rumps.notification("Automation Complete", "", "Check logs for details"))
            except Exception as e:
                ui_call(lambda: rumps.notification("Automation Failed", "", f"Error: {e}"))
            finally:
                self.running = False
                self.update_menu_status()
        
        self.job_thread = threading.Thread(target=run_thread, daemon=True)
        self.job_thread.start()
    
    def stop_automation_action(self, sender):
        """Stop the running automation."""
        rumps.alert("Stop Automation", "Graceful stop not implemented. Close the browser window to stop.")
    
    def open_logs_folder(self, sender):
        """Open logs folder in Finder."""
        subprocess.call(['open', str(LOGS_DIR)])
    
    def open_screenshots_folder(self, sender):
        """Open screenshots folder in Finder."""
        subprocess.call(['open', str(SCREENSHOTS_DIR)])
    
    def open_configs_folder(self, sender):
        """Open configs folder in Finder."""
        subprocess.call(['open', str(CONFIGS_DIR)])
    
    def quit_app(self, sender):
        """Quit the application."""
        if self.running:
            response = rumps.alert("Automation Running", "Quit anyway?", ok="Quit", cancel="Cancel")
            if response == 0:
                return
        
        rumps.quit_application()


def is_already_running():
    """Check if another instance is already running."""
    lock_file = APP_SUPPORT_DIR / ".lock"
    
    if lock_file.exists():
        try:
            with open(lock_file, "r") as f:
                pid = int(f.read().strip())
            
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                lock_file.unlink()
                return False
        except (ValueError, FileNotFoundError):
            lock_file.unlink()
            return False
    
    return False


def create_lock_file():
    """Create a lock file with current PID."""
    lock_file = APP_SUPPORT_DIR / ".lock"
    with open(lock_file, "w") as f:
        f.write(str(os.getpid()))


def remove_lock_file():
    """Remove the lock file."""
    lock_file = APP_SUPPORT_DIR / ".lock"
    if lock_file.exists():
        lock_file.unlink()


def _self_test() -> int:
    """Run a non-GUI self-test that prints readiness + missing prerequisites.

    Returns process exit code (0 = ready, 1 = not ready).
    """
    setup_app_support()

    # Load persisted state without constructing the rumps UI.
    selected_config = None
    csv_path = None
    options = {
        'headless': False,
        'dry_run': False,
        'no_save': False,
        'debug': False,
        'start_version': None,
        'limit': None,
    }
    try:
        if STATE_FILE_PATH.exists():
            with open(STATE_FILE_PATH, 'r') as f:
                state = json.load(f)
            selected_config = state.get('selected_config')
            csv_path = state.get('csv_path')
            options.update(state.get('options', {}))
    except Exception as e:
        print(f"WARN: failed to load state: {e}")

    # Default config if nothing selected.
    if not selected_config and (CONFIGS_DIR / "default.json").exists():
        selected_config = "default"

    chromium_installed = check_chromium_installed()
    session_valid = is_session_valid()

    missing = []
    if not selected_config:
        missing.append("Config not selected")
    if not csv_path:
        missing.append("CSV not selected")
    if not chromium_installed:
        missing.append("Chromium not installed")
    if not session_valid:
        missing.append("Session not valid (run Setup Login)")

    details = [
        f"Chromium installed: {chromium_installed}",
        f"Session valid: {session_valid}",
        f"Selected config: {selected_config or 'None'}",
        f"CSV: {Path(csv_path).name if csv_path else 'None'}",
        f"Browser visible: {not options.get('headless', False)}",
        f"Dry run: {options.get('dry_run', False)}",
        f"No save: {options.get('no_save', False)}",
        f"Debug: {options.get('debug', False)}",
        f"AppSupport: {APP_SUPPORT_DIR}",
        f"ConfigsDir: {CONFIGS_DIR}",
    ]

    if missing:
        print("NOT READY\n")
        print("Missing:")
        for m in missing:
            print(f"- {m}")
        print("\nDetails:")
        print("\n".join(details))
        return 1

    print("READY\n")
    print("Details:")
    print("\n".join(details))
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AnyLiveTTS Menu Bar App")
    parser.add_argument("--self-test", action="store_true", help="Run non-GUI readiness checks and exit")
    args = parser.parse_args()

    if args.self_test:
        raise SystemExit(_self_test())

    setup_app_support()

    if is_already_running():
        rumps.alert("Already Running", "AnyLive TTS is already running. Check your menu bar.", ok="OK")
        sys.exit(0)

    create_lock_file()

    try:
        app = AnyLiveTTSApp()
        app.run()
    finally:
        remove_lock_file()
