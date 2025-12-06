import socket
import re
import time
import json
import os
import sys
import threading
import requests
import webbrowser
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item
from pypresence import Presence
from bs4 import BeautifulSoup

# ==================== RESOURCE PATH HELPER ====================
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ==================== CONFIGURATION & CONSTANTS ====================
CONFIG_FILE = "config.json"
CACHE_FILE = "ps5_cache.json"
LANG_FILE = resource_path("languages.json")
ICON_FILE = resource_path("icon.ico")
KLOG_PORT = 9081

DEFAULT_CONFIG = {
    "ps5_ip": "",
    "client_id": "",
    "language": "en"
}

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

SYSTEM_TITLES = {
    "ITEM00001": {"name": "Main Menu", "image": "ps5"},
    "CUSA00001": {"name": "Media Player", "image": "ps5"},
    "PPSA00001": {"name": "PlayStation Store", "image": "ps5"},
    "CUSA00002": {"name": "Troféus", "image": "ps5"}
}

TITLE_PATTERN = re.compile(r"title_id\s*=\s*[\[\'\s]([A-Z0-9]{9,})[\]\'\s]")

# ==================== FILE MANAGEMENT ====================

def load_json(file, default=None):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if default: return {**default, **data}
                return data
        except: pass
    
    if default is not None:
        save_json(file, default)
        return default
    return None

def save_json(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

languages = load_json(LANG_FILE)
if languages is None:
    root = ctk.CTk()
    root.withdraw()
    messagebox.showerror("Fatal Error", f"File '{LANG_FILE}' not found!\n\nThe application cannot start without the language file.")
    sys.exit()

config = load_json(CONFIG_FILE, DEFAULT_CONFIG)
game_cache = load_json(CACHE_FILE, {})

def tr(key):
    lang_code = config.get("language", "en")
    lang_dict = languages.get(lang_code, languages.get("en", {}))
    return lang_dict.get(key, key)

# ==================== WEB SCRAPING ====================

def fetch_online_data(title_id):
    ps4_prefixes = (
        "CUSA", "CUSJ", "CUSK", "CUSC", "CUSH", "CUSE", 
        "PLAS", "PLJM", "PCJS"
    )

    if title_id.startswith(ps4_prefixes):
        base_url = "https://orbispatches.com"
        print(tr("log_detect_ps4").format(id=title_id))
    else:
        base_url = "https://prosperopatches.com"
        print(tr("log_detect_ps5").format(id=title_id))
        
    url = f"{base_url}/{title_id}"

    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        
        if r.status_code != 200: 
            print(tr("log_http_error").format(code=r.status_code, url=url))
            return None

        soup = BeautifulSoup(r.text, 'html.parser')
        
        game_name = None

        title_tag = soup.select_one("h1.bd-title")
        if title_tag:
            game_name = title_tag.get_text(strip=True)

        if not game_name:
            logo_img = soup.select_one("div.flex-fill img[alt]")
            if logo_img and logo_img["alt"].strip():
                game_name = logo_img["alt"].strip()
                print(tr("log_alt_name").format(name=game_name))

        if not game_name:
            page_title = soup.find("title")
            if page_title:
                game_name = page_title.get_text(strip=True).split(" - ")[0]
            else:
                game_name = title_id

        image_url = "ps5"
        icon_div = soup.select_one("div.game-icon.secondary")
        
        if icon_div and icon_div.has_attr("style"):
            match = re.search(r'url\((?:&quot;|")?(.*?)(?:&quot;|")?\)', icon_div["style"])
            if match: 
                image_url = match.group(1)
                if image_url.startswith("/"):
                    image_url = base_url + image_url
        
        return {"name": game_name, "image": image_url}

    except Exception as e:
        print(tr("log_scraping_error").format(error=e))
        return None

def get_game_info(title_id):
    if title_id in SYSTEM_TITLES: return SYSTEM_TITLES[title_id]
    if title_id in game_cache: return game_cache[title_id]
    
    data = fetch_online_data(title_id)
    if data:
        game_cache[title_id] = data
        save_json(CACHE_FILE, game_cache)
        return data
    
    return {"name": tr("game_unknown").format(id=title_id), "image": "ps5"}

# ==================== GUI ====================

class ExitDialog(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title(tr("exit_title"))
        self.geometry("300x150")
        self.resizable(False, False)
        
        if os.path.exists(ICON_FILE):
            self.iconbitmap(ICON_FILE)

        self.result = None
        
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 150
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 75
        self.geometry(f"+{x}+{y}")

        self.label = ctk.CTkLabel(self, text=tr("exit_msg"), font=("Roboto", 14))
        self.label.pack(pady=20)

        self.btn_minimize = ctk.CTkButton(self, text=tr("btn_minimize"), command=self.minimize, fg_color="#2CC985", hover_color="#229A65")
        self.btn_minimize.pack(pady=5, padx=20, fill="x")

        self.btn_close = ctk.CTkButton(self, text=tr("btn_close"), command=self.close_app, fg_color="#C92C2C", hover_color="#9A2222")
        self.btn_close.pack(pady=5, padx=20, fill="x")
        self.grab_set()

    def minimize(self):
        self.result = "minimize"
        self.destroy()

    def close_app(self):
        self.result = "close"
        self.destroy()

class PS5App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(tr("window_title"))
        self.geometry("600x550")
        self.resizable(False, False)
        self.center_window(600, 550)
        
        if os.path.exists(ICON_FILE):
            self.iconbitmap(ICON_FILE)

        self.running = True
        self.rpc = None
        self.current_title_id = None
        self.tray_icon = None
        self.reconnect_requested = False
        self.is_minimized_to_tray = False
        
        initial_ip = config.get("ps5_ip", "")
        initial_id = config.get("client_id", "")
        initial_lang = config.get("language", "en")

        self.ready_to_connect = bool(initial_ip and initial_id)

        self.ps5_ip_var = ctk.StringVar(value=initial_ip)
        self.client_id_var = ctk.StringVar(value=initial_id)
        self.lang_var = ctk.StringVar(value=initial_lang)

        self.protocol("WM_DELETE_WINDOW", self.on_close_button)
        self.bind("<Unmap>", self.on_minimize_event)

        self.create_widgets()
        
        self.monitor_thread = threading.Thread(target=self.run_monitor, daemon=True)
        self.monitor_thread.start()

        self.tray_thread = threading.Thread(target=self.setup_tray, daemon=True)
        self.tray_thread.start()
        
        if not self.ready_to_connect:
            self.log(tr("log_missing"))
            self.lbl_status.configure(text=tr("status_waiting"), text_color="orange")
        else:
            self.log(tr("log_found"))

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f'{width}x{height}+{x}+{y}')

    def open_discord_dev(self, event):
        webbrowser.open("https://discord.com/developers/applications/")

    def create_widgets(self):
        self.config_frame = ctk.CTkFrame(self)
        self.config_frame.pack(pady=10, padx=10, fill="x")
        
        ctk.CTkLabel(self.config_frame, text=tr("lbl_config"), font=("Roboto", 14, "bold")).pack(pady=(5,0))
        
        self.grid_frame = ctk.CTkFrame(self.config_frame, fg_color="transparent")
        self.grid_frame.pack(pady=5, padx=5, fill="x")

        ctk.CTkLabel(self.grid_frame, text=tr("lbl_ip")).grid(row=0, column=0, padx=5, sticky="w")
        self.entry_ip = ctk.CTkEntry(self.grid_frame, textvariable=self.ps5_ip_var, width=150)
        self.entry_ip.grid(row=0, column=1, padx=5, pady=5)

        self.lbl_id_link = ctk.CTkLabel(
            self.grid_frame, 
            text=tr("lbl_id"), 
            text_color="#4cc2ff", 
            cursor="hand2"
        )
        self.lbl_id_link.grid(row=0, column=2, padx=5, sticky="w")
        self.lbl_id_link.bind("<Button-1>", self.open_discord_dev)

        self.entry_id = ctk.CTkEntry(self.grid_frame, textvariable=self.client_id_var, width=180)
        self.entry_id.grid(row=0, column=3, padx=5, pady=5)
        
        ctk.CTkLabel(self.grid_frame, text=tr("lbl_lang")).grid(row=1, column=0, padx=5, sticky="w")
        available_langs = list(languages.keys())
        self.combo_lang = ctk.CTkOptionMenu(self.grid_frame, values=available_langs, variable=self.lang_var)
        self.combo_lang.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        self.btn_save = ctk.CTkButton(self.config_frame, text=tr("btn_save"), command=self.save_settings, height=30)
        self.btn_save.pack(pady=10, padx=20, fill="x")

        self.header_frame = ctk.CTkFrame(self)
        self.header_frame.pack(pady=5, padx=10, fill="x")
        
        self.lbl_status_title = ctk.CTkLabel(self.header_frame, text=tr("lbl_status_title"), font=("Roboto", 12, "bold"))
        self.lbl_status_title.pack(side="left", padx=10)
        
        self.lbl_status = ctk.CTkLabel(self.header_frame, text=tr("status_starting"), text_color="orange")
        self.lbl_status.pack(side="left", padx=5)

        self.log_box = ctk.CTkTextbox(self, width=580, height=280, font=("Consolas", 12))
        self.log_box.pack(pady=10, padx=10)
        self.log_box.configure(state="disabled")

        self.lbl_info = ctk.CTkLabel(self, text="MestreTM - v1.0", text_color="gray", font=("Arial", 10), cursor="hand2")
        self.lbl_info.bind("<Button-1>", lambda e: webbrowser.open("https://github.com/MestreTM"))
        self.lbl_info.pack(side="bottom", pady=5)

    def log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{time.strftime('%H:%M:%S')}] {message}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def save_settings(self):
        new_ip = self.ps5_ip_var.get().strip()
        new_id = self.client_id_var.get().strip()
        new_lang = self.lang_var.get()
        
        if not new_ip or not new_id:
            self.log(tr("log_error_empty"))
            return

        old_lang = config.get("language")
        
        config["ps5_ip"] = new_ip
        config["client_id"] = new_id
        config["language"] = new_lang
        save_json(CONFIG_FILE, config)
        
        self.log(tr("log_saved"))
        
        if old_lang != new_lang:
             self.log(tr("log_lang_changed"))
        
        self.ready_to_connect = True
        self.reconnect_requested = True
        if self.rpc:
            try: 
                self.rpc.clear()
                self.rpc.close()
            except: pass
            self.rpc = None

    def connect_discord(self):
        current_id = config["client_id"]
        try:
            self.rpc = Presence(current_id)
            self.rpc.connect()
            self.log(f"{tr('log_discord_ok')} (ID: {current_id[:4]}...)")
            return True
        except: return False

    def update_rpc(self, title_id):
        if title_id == self.current_title_id: return
        data = get_game_info(title_id)
        self.current_title_id = title_id
        start_time = int(time.time())
        
        self.log(f"{tr('log_game_detected')} {data['name']}")
        self.lbl_status.configure(text=f"{tr('status_playing')} {data['name']}", text_color="#00ff00")
        
        if self.rpc:
            try:
                image = data['image'] if data['image'] and "http" in data['image'] else "ps5"
                if len(image) > 256: image = "ps5"
                
                self.rpc.update(
                    details=tr("rpc_details"), 
                    state=data['name'], 
                    large_image=image, 
                    large_text=data['name'], 
                    small_image="ps5", 
                    small_text=tr("rpc_small_text"),
                    start=start_time
                )
            except: pass

    def run_monitor(self):
        while self.running:
            if not self.ready_to_connect:
                time.sleep(1)
                continue
            if not self.rpc: self.connect_discord()
            ip = config["ps5_ip"]
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(10)
                s.connect((ip, KLOG_PORT))
                self.log(f"{tr('log_connected_klog')} ({ip})")
                self.lbl_status.configure(text=tr("status_connected"), text_color="#4cc2ff")
                self.reconnect_requested = False
                buffer = ""
                last_packet = time.time()
                while self.running and not self.reconnect_requested:
                    try:
                        data = s.recv(4096).decode("utf-8", errors="ignore")
                        if not data: break
                        buffer += data
                        last_packet = time.time()
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            match = TITLE_PATTERN.search(line)
                            if match: self.update_rpc(match.group(1))
                        if time.time() - last_packet > 120 and self.current_title_id:
                            self.current_title_id = None
                            if self.rpc: self.rpc.clear()
                            self.lbl_status.configure(text=tr("status_idle"), text_color="orange")
                    except socket.timeout: continue 
                    except OSError: break 
            except:
                self.lbl_status.configure(text=tr("status_disconnected"), text_color="red")
                time.sleep(5)
            finally:
                try: s.close()
                except: pass
            if self.reconnect_requested: time.sleep(1)

    def create_image(self):
        width = 64; height = 64
        image = Image.new('RGB', (width, height), (30, 30, 30))
        dc = ImageDraw.Draw(image)
        dc.rectangle((20, 20, 44, 44), fill="#4cc2ff")
        return image

    def setup_tray(self):
        if os.path.exists(ICON_FILE):
            try:
                image = Image.open(ICON_FILE)
            except:
                image = self.create_image()
        else:
            image = self.create_image()
            
        menu = (item(tr('tray_open'), self.show_window, default=True), item(tr('tray_exit'), self.quit_app_tray))
        self.tray_icon = pystray.Icon("PS5RPC", image, tr('tray_title'), menu)
        self.tray_icon.run()

    def on_minimize_event(self, event):
        if event.widget == self and self.state() == 'iconic':
            if not self.is_minimized_to_tray:
                self.hide_to_tray()

    def on_close_button(self):
        dialog = ExitDialog(self)
        self.wait_window(dialog)
        
        if dialog.result == "minimize":
            self.hide_to_tray()
        elif dialog.result == "close":
            self.quit_app()

    def hide_to_tray(self):
        self.is_minimized_to_tray = True
        self.withdraw() 
        if self.tray_icon:
            self.tray_icon.notify(tr("tray_msg"), tr("tray_title"))

    def show_window(self, icon, item):
        self.is_minimized_to_tray = False
        self.deiconify() 
        self.lift()      
        self.state('normal')

    def quit_app_tray(self, icon, item):
        self.quit_app()

    def quit_app(self):
        self.running = False
        if self.tray_icon: self.tray_icon.stop()
        self.quit()
        os._exit(0)

if __name__ == "__main__":
    app = PS5App()
    app.mainloop()
