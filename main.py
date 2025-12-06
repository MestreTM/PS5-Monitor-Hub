import sys
import threading
import time
import signal

from app.utils import ConfigManager, Logger
from app.core import PS5Core
from app.discord import DiscordHandler
from app.haos import HAOSHandler
from app.plugin_manager import PluginManager

HEADLESS_MODE = "--nogui" in sys.argv
ICON_FILE = "icon.ico"

if not HEADLESS_MODE:
    import customtkinter as ctk
    from PIL import Image
    import pystray
    from pystray import MenuItem as item
    import os

    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")

class HeadlessApp:
    def __init__(self):
        self.config = ConfigManager()
        self.discord_handler = DiscordHandler()
        self.haos_handler = HAOSHandler()
        self.plugin_manager = PluginManager()
        
        self.core = PS5Core(self.on_core_update)
        self.running = True

        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)

    def run(self):
        Logger.log("Starting PS5 Monitor (Headless Mode)...")
        
        self.plugin_manager.discover_plugins()
        for plugin in self.plugin_manager.get_plugins():
            manifest = plugin.get_manifest()
            pid = manifest['id']
            p_config = self.config.get("plugins", pid) or {}
            plugin.on_load(p_config)

        if self.config.get("discord", "enabled"): self.discord_handler.connect()
        if self.config.get("haos", "enabled"): self.haos_handler.connect()
        
        self.core.start()
        
        while self.running:
            time.sleep(1)

    def on_core_update(self, data):
        self.discord_handler.update(data)
        self.haos_handler.update(data)
        
        for plugin in self.plugin_manager.get_plugins():
            try: plugin.on_update(data)
            except Exception as e: Logger.log(f"Plugin Error: {e}")

        status = data.get("status")
        game = data.get("game", {})
        if status in ['Playing', 'Online']:
             Logger.log(f"Update: {status} - {game.get('name', 'Unknown')}")

    def shutdown(self, signum, frame):
        Logger.log("Shutting down...")
        self.running = False
        self.core.stop()
        self.discord_handler.disconnect()
        self.haos_handler.disconnect()
        for plugin in self.plugin_manager.get_plugins():
            plugin.on_unload()
        sys.exit(0)

if not HEADLESS_MODE:
    
    class ExitDialog(ctk.CTkToplevel):
        def __init__(self, parent):
            super().__init__(parent)
            self.title("Exit PS5 Monitor")
            self.geometry("300x150")
            self.resizable(False, False)
            self.result = None

            if os.path.exists(ICON_FILE):
                self.iconbitmap(ICON_FILE)

            self.update_idletasks()
            x = parent.winfo_x() + (parent.winfo_width() // 2) - 150
            y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
            self.geometry(f"+{x}+{y}")

            self.label = ctk.CTkLabel(self, text="What would you like to do?", font=("Arial", 14))
            self.label.pack(pady=20)

            self.btn_minimize = ctk.CTkButton(self, text="Minimize to Tray", command=self.minimize, fg_color="#2CC985", hover_color="#229A65")
            self.btn_minimize.pack(pady=5, padx=20, fill="x")

            self.btn_close = ctk.CTkButton(self, text="Close Application", command=self.close_app, fg_color="#C92C2C", hover_color="#9A2222")
            self.btn_close.pack(pady=5, padx=20, fill="x")
            
            self.transient(parent)
            self.grab_set()

        def minimize(self):
            self.result = "minimize"
            self.destroy()

        def close_app(self):
            self.result = "close"
            self.destroy()

    class GUIApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("PS5 Monitor Hub")
            self.geometry("700x600")
            self.resizable(False, False)
            self.center_window(700, 600)
            
            if os.path.exists(ICON_FILE):
                self.iconbitmap(ICON_FILE)

            Logger.set_callback(self.log_gui_safe)

            self.config = ConfigManager()
            self.discord_handler = DiscordHandler()
            self.haos_handler = HAOSHandler()
            self.plugin_manager = PluginManager()
            
            self.core = PS5Core(self.on_core_update)
            
            self.protocol("WM_DELETE_WINDOW", self.on_close_request)
            self.bind("<Unmap>", self.on_minimize_event)
            self.is_minimized_to_tray = False
            self.tray_icon = None

            self.plugin_widgets = {} 
            self.plugin_tab_names = []

            self.create_widgets()
            
            self.last_logged_game = None
            self.after(200, self.start_services_background)

        def start_services_background(self):
            threading.Thread(target=self._connect_services, daemon=True).start()

        def _connect_services(self):
            self.reload_plugins_logic()

            if self.config.get("discord", "enabled"): 
                self.discord_handler.connect()
            
            if self.config.get("haos", "enabled"): 
                self.haos_handler.connect()
            
            self.core.start()

        def reload_plugins_logic(self):
            self.log_gui_safe("Scanning plugins...")
            self.plugin_manager.unload_all()
            self.plugin_manager.discover_plugins()
            self._init_plugins_config()
            self.after(0, self._refresh_plugin_tabs)

        def _init_plugins_config(self):
            for plugin in self.plugin_manager.get_plugins():
                pid = plugin.get_manifest()['id']
                saved_cfg = self.config.get("plugins", pid) or {}
                
                defaults = {f['key']: f['default'] for f in plugin.get_manifest()['fields']}
                defaults['enabled'] = False
                
                final_cfg = {**defaults, **saved_cfg}
                plugin.on_load(final_cfg)

        def _refresh_plugin_tabs(self):
            for name in self.plugin_tab_names:
                try: self.tabview.delete(name)
                except: pass
            self.plugin_tab_names = []
            self.plugin_widgets = {}

            self._render_plugin_tabs()
            self.log_gui_safe(f"Loaded {len(self.plugin_manager.get_plugins())} plugins.")

        def _render_plugin_tabs(self):
            for plugin in self.plugin_manager.get_plugins():
                manifest = plugin.get_manifest()
                pid = manifest['id']
                p_name = manifest['name']
                
                tab_title = f"🧩 {p_name}"
                
                try:
                    self.tabview.add(tab_title)
                    self.plugin_tab_names.append(tab_title)
                    tab = self.tabview.tab(tab_title)
                except ValueError: continue

                self.plugin_widgets[pid] = {}

                ctk.CTkLabel(tab, text=f"{p_name}", font=("Arial", 16, "bold")).pack(pady=5)
                ctk.CTkLabel(tab, text=manifest.get("description", ""), text_color="gray").pack(pady=(0, 10))

                chk_var = ctk.BooleanVar(value=plugin.config.get("enabled", False))
                chk = ctk.CTkCheckBox(tab, text=f"Enable Plugin", variable=chk_var)
                chk.pack(pady=5)
                self.plugin_widgets[pid]["enabled"] = chk_var

                for field in manifest['fields']:
                    f_key = field['key']
                    f_type = field['type']
                    f_val = plugin.config.get(f_key, field['default'])

                    frame = ctk.CTkFrame(tab, fg_color="transparent")
                    frame.pack(pady=2, fill="x", padx=20)

                    if f_type == "checkbox":
                        var = ctk.BooleanVar(value=bool(f_val))
                        w = ctk.CTkCheckBox(frame, text=field['label'], variable=var)
                        w.pack(anchor="w")
                        self.plugin_widgets[pid][f_key] = var
                    else:
                        ctk.CTkLabel(frame, text=field['label'], width=100, anchor="w").pack(side="left")
                        show_char = "*" if f_type == "password" else None
                        w = ctk.CTkEntry(frame, width=250, show=show_char)
                        w.insert(0, str(f_val))
                        w.pack(side="right", expand=True, fill="x")
                        self.plugin_widgets[pid][f_key] = w

                btn = ctk.CTkButton(tab, text="Save Settings", 
                                    command=lambda p=plugin: self.save_plugin(p))
                btn.pack(pady=20)
                self.plugin_widgets[pid]["btn"] = btn

        def save_plugin(self, plugin):
            manifest = plugin.get_manifest()
            pid = manifest['id']
            widgets = self.plugin_widgets.get(pid)
            if not widgets: return

            new_config = {}
            new_config["enabled"] = widgets["enabled"].get()

            for field in manifest['fields']:
                key = field['key']
                widget = widgets[key]
                if isinstance(widget, ctk.BooleanVar):
                    new_config[key] = widget.get()
                elif isinstance(widget, ctk.CTkEntry):
                    new_config[key] = widget.get()

            self.config.set("plugins", pid, new_config)
            plugin.on_load(new_config)
            
            self._animate_save_button(widgets["btn"], "Save Settings")
            self.log_gui_safe(f"Saved: {manifest['name']}")

        def center_window(self, width, height):
            screen_width = self.winfo_screenwidth()
            screen_height = self.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.geometry(f'{width}x{height}+{x}+{y}')

        def log_gui_safe(self, message):
            self.after(0, lambda: self._internal_log_write(message))

        def _internal_log_write(self, message):
            self.log_textbox.configure(state="normal")
            if not message.endswith("\n"): message += "\n"
            self.log_textbox.insert("end", message)
            self.log_textbox.see("end")
            self.log_textbox.configure(state="disabled")

        def _animate_save_button(self, button, original_text):
            button.configure(text="Saved!")
            self.after(2000, lambda: button.configure(text=original_text))

        def on_core_update(self, data):
            self.discord_handler.update(data)
            self.haos_handler.update(data)
            
            for plugin in self.plugin_manager.get_plugins():
                try: plugin.on_update(data)
                except: pass

            self.after(0, lambda: self.update_gui_elements(data))

        def update_gui_elements(self, data):
            game_name = data["game"].get("name", "None")
            title_id = data["game"].get("title_id", "")
            status = data["status"]
            
            status_text = f"Status: {status} | App: {game_name}"
            stats_text = f"CPU: {data['stats'].get('cpu_temp')} | SoC: {data['stats'].get('soc_temp')}"
            
            self.lbl_status_bar.configure(text=f"{status_text}\n{stats_text}")
            
            if status in ['Playing', 'Online'] and title_id:
                if self.last_logged_game != title_id:
                    self.last_logged_game = title_id
            elif status == 'Idle' and self.last_logged_game != 'Idle':
                self.last_logged_game = 'Idle'

        def create_widgets(self):
            self.tabview = ctk.CTkTabview(self, width=680, height=500)
            self.tabview.pack(pady=10, padx=10)
            
            tab_gen = self.tabview.add("General")
            tab_disc = self.tabview.add("Discord")
            tab_haos = self.tabview.add("Home Assistant")
            
            # === GENERAL TAB ===
            ctk.CTkLabel(tab_gen, text="PS5 Settings", font=("Arial", 16, "bold")).pack(pady=10)
            self.entry_ip = self.create_input(tab_gen, "PS5 IP:", self.config.get("general", "ps5_ip"))
            
            self.btn_reload = ctk.CTkButton(tab_gen, text="Reload Plugins", command=self.btn_reload_click, fg_color="#E0A800", hover_color="#B08400")
            self.btn_reload.pack(pady=(20, 5))

            self.btn_gen = ctk.CTkButton(tab_gen, text="Save General", command=self.save_general)
            self.btn_gen.pack(pady=5)
            
            self.log_textbox = ctk.CTkTextbox(tab_gen, width=600, height=150)
            self.log_textbox.pack(pady=10)
            self.log_textbox.insert("0.0", "System logs started...\n")
            self.log_textbox.configure(state="disabled") 

            # === DISCORD TAB ===
            self.chk_discord = ctk.CTkCheckBox(tab_disc, text="Enable Discord RPC")
            if self.config.get("discord", "enabled"): self.chk_discord.select()
            self.chk_discord.pack(pady=10)
            
            self.entry_client_id = self.create_input(tab_disc, "Client ID:", self.config.get("discord", "client_id"))
            
            self.btn_disc = ctk.CTkButton(tab_disc, text="Save Discord", command=self.save_discord)
            self.btn_disc.pack(pady=20)

            # === HAOS TAB ===
            self.chk_haos = ctk.CTkCheckBox(tab_haos, text="Enable MQTT (HAOS)")
            if self.config.get("haos", "enabled"): self.chk_haos.select()
            self.chk_haos.pack(pady=10)
            
            self.entry_broker = self.create_input(tab_haos, "Broker IP:", self.config.get("haos", "mqtt_broker"))
            self.entry_mqtt_user = self.create_input(tab_haos, "User:", self.config.get("haos", "mqtt_user"))
            self.entry_mqtt_pass = self.create_input(tab_haos, "Password:", self.config.get("haos", "mqtt_pass"), show="*")
            self.entry_topic = self.create_input(tab_haos, "Topic:", self.config.get("haos", "mqtt_topic"))
            
            self.btn_haos = ctk.CTkButton(tab_haos, text="Save HAOS", command=self.save_haos)
            self.btn_haos.pack(pady=20)

            # === FOOTER ===
            self.lbl_status_bar = ctk.CTkLabel(self, text="Waiting for connection...", text_color="gray")
            self.lbl_status_bar.pack(side="bottom", pady=5)

        def create_input(self, parent, label, value, show=None):
            frame = ctk.CTkFrame(parent, fg_color="transparent")
            frame.pack(pady=5)
            ctk.CTkLabel(frame, text=label, width=100, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(frame, width=250, show=show)
            entry.insert(0, str(value) if value else "")
            entry.pack(side="left")
            return entry

        def btn_reload_click(self):
            threading.Thread(target=self.reload_plugins_logic, daemon=True).start()

        def save_general(self):
            self.config.set("general", "ps5_ip", self.entry_ip.get())
            self.log_gui_safe("General Settings Saved.")
            threading.Thread(target=self._reload_core_service, daemon=True).start()
            self._animate_save_button(self.btn_gen, "Save General")

        def _reload_core_service(self):
            self.after(0, lambda: self.log_gui_safe("Reloading PS5 Core Service..."))
            self.core.stop()
            time.sleep(1)
            self.core.start()
            self.after(0, lambda: self.log_gui_safe("PS5 Core Service Reloaded."))

        def save_discord(self):
            enabled = bool(self.chk_discord.get())
            self.config.set("discord", "enabled", enabled)
            self.config.set("discord", "client_id", self.entry_client_id.get())
            threading.Thread(target=self._reload_discord_service, args=(enabled,), daemon=True).start()
            self._animate_save_button(self.btn_disc, "Save Discord")

        def _reload_discord_service(self, enabled):
            self.discord_handler.disconnect()
            if enabled: 
                self.after(0, lambda: self.log_gui_safe("Reconnecting Discord..."))
                self.discord_handler.connect()
                self.after(0, lambda: self.log_gui_safe("Discord Connected."))
            else:
                self.after(0, lambda: self.log_gui_safe("Discord Disabled."))

        def save_haos(self):
            enabled = bool(self.chk_haos.get())
            self.config.set("haos", "enabled", enabled)
            self.config.set("haos", "mqtt_broker", self.entry_broker.get())
            self.config.set("haos", "mqtt_user", self.entry_mqtt_user.get())
            self.config.set("haos", "mqtt_pass", self.entry_mqtt_pass.get())
            self.config.set("haos", "mqtt_topic", self.entry_topic.get())
            threading.Thread(target=self._reload_haos_service, args=(enabled,), daemon=True).start()
            self._animate_save_button(self.btn_haos, "Save HAOS")

        def _reload_haos_service(self, enabled):
            self.haos_handler.disconnect()
            if enabled: 
                self.after(0, lambda: self.log_gui_safe("Reconnecting MQTT..."))
                self.haos_handler.connect()
                self.after(0, lambda: self.log_gui_safe("MQTT Enabled."))
            else:
                self.after(0, lambda: self.log_gui_safe("MQTT Disabled."))

        def on_close_request(self):
            dialog = ExitDialog(self)
            self.wait_window(dialog)
            if dialog.result == "minimize": self.hide_to_tray()
            elif dialog.result == "close": self.quit_app()

        def on_minimize_event(self, event):
            if event.widget == self and self.state() == 'iconic':
                if not self.is_minimized_to_tray: self.hide_to_tray()

        def hide_to_tray(self):
            self.is_minimized_to_tray = True
            self.withdraw()
            
            if not self.tray_icon:
                if os.path.exists(ICON_FILE): 
                    try: image = Image.open(ICON_FILE)
                    except: image = Image.new('RGB', (64, 64), (50, 50, 50))
                else:
                    image = Image.new('RGB', (64, 64), (50, 50, 50))
                
                menu = (item('Open', self.show_window, default=True), item('Exit', self.quit_app_tray))
                self.tray_icon = pystray.Icon("PS5Mon", image, "PS5 Monitor", menu)
                threading.Thread(target=self.tray_icon.run, daemon=True).start()
            
            try: self.tray_icon.notify("Application minimized to tray.", "PS5 Monitor")
            except: pass

        def show_window(self, icon, item):
            self.is_minimized_to_tray = False
            self.deiconify()
            self.center_window(700, 600)
            self.lift()
            self.state('normal')

        def quit_app_tray(self, icon, item):
            self.quit_app()

        def quit_app(self):
            self.core.stop()
            if self.tray_icon: self.tray_icon.stop()
            self.quit()
            sys.exit()

if __name__ == "__main__":
    if HEADLESS_MODE:
        app = HeadlessApp()
        app.run()
    else:
        app = GUIApp()
        app.mainloop()