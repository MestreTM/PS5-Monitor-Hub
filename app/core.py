import socket
import re
import time
import threading
import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .utils import ConfigManager, Logger, load_cache, save_cache

# === REGEX PATTERNS ===
SCENE_PATTERN = re.compile(r"OnFocusActiveSceneChanged\s*\[(.*?)\]\s*->\s*\[(.*?)\]")
ID_EXTRACTOR = re.compile(r"(?:Render\.|titleId\s*[:=]\s*|title_id\s*=\s*['\"\[]?|SplashScreen\.)([A-Z]{4}[0-9]{5})", re.IGNORECASE)
DEBUG_PATTERN = re.compile(r"id_debug_settings")
PROHIBITION_PATTERN = re.compile(r"ProhibitionFlag.*?newFlags\s*=\s*\[.*?,([A-Z]{4}[0-9]{5}),\]")

# === IGNORED PROCESSES (Background/Dialogs/Overlays) ===
IGNORED_IDS = {
    "NPXS40003", "NPXS40093", "NPXS40094", "NPXS40095", "NPXS40096", 
    "NPXS40100", "NPXS40109", "NPXS40112"
}

SYSTEM_TITLES = {
    "NPXS40002": {"name": "Home Menu", "image": "ps5", "background": ""},
    "NPXS40008": {"name": "Settings", "image": "settings", "background": ""},
    "DEBUG_SETTINGS": {"name": "Debug Settings", "image": "cog", "background": ""},
    "ITEM00001": {"name": "Launching...", "image": "ps5", "background": ""},
    "CUSA00001": {"name": "Media Player", "image": "play", "background": ""},
    "PPSA00001": {"name": "PlayStation Store", "image": "store", "background": ""},
    "CUSA00002": {"name": "Trophies", "image": "trophy", "background": ""}
}

class PS5Core:
    def __init__(self, callback_update):
        self.config = ConfigManager()
        self.running = False
        self.callback_update = callback_update
        self.game_cache = load_cache()
        self.current_title_id = None
        
        self.last_status = "Offline"
        self.last_game_info = {}
        self.current_stats = {"cpu_temp": "N/A", "soc_temp": "N/A", "frequency": "N/A"}
        
        # === TIME PERSISTENCE SYSTEM ===
        # Stores the start timestamp of the current game session
        self.active_game_id = None
        self.active_game_start_time = None

    def start(self):
        self.running = True
        threading.Thread(target=self._monitor_klog, daemon=True).start()
        threading.Thread(target=self._monitor_stats, daemon=True).start()

    def stop(self):
        self.running = False

    def _monitor_stats(self):
        while self.running:
            ip = self.config.get("general", "ps5_ip")
            port = self.config.get("general", "stats_port")
            
            if not ip: 
                time.sleep(5)
                continue

            url = f"http://{ip}:{port}"
            SELECTORS = {
                "cpu_temp": 'div.info-label:text("CPU Temp") + div.info-value',
                "soc_temp": 'div.info-label:text("SoC Temp") + div.info-value',
                "frequency": 'div.info-label:text("Frequency") + div.info-value'
            }

            try:
                with sync_playwright() as p:
                    browser = p.chromium.launch(headless=True)
                    page = browser.new_page()
                    
                    while self.running:
                        try:
                            page.goto(url, timeout=5000)
                            try: page.wait_for_selector('div.system-info-content', timeout=3000)
                            except: pass
                            
                            new_stats = {}
                            for key, selector in SELECTORS.items():
                                try:
                                    if page.locator(selector).count() > 0:
                                        val = page.locator(selector).first.inner_text()
                                        new_stats[key] = val.strip()
                                    else: new_stats[key] = "N/A"
                                except: new_stats[key] = "N/A"

                            self.current_stats = new_stats
                            self._notify()

                        except PlaywrightTimeoutError:
                            self.current_stats = {"cpu_temp": "Timeout", "soc_temp": "Timeout", "frequency": "Timeout"}
                        except Exception:
                            self.current_stats = {"cpu_temp": "Err Conn", "soc_temp": "Err Conn", "frequency": "Err Conn"}
                        
                        for _ in range(10): 
                            if not self.running: break
                            time.sleep(1)
                    browser.close()
            except Exception as e:
                Logger.log(f"Playwright Error: {e}")
                time.sleep(60)

    def _monitor_klog(self):
        while self.running:
            ip = self.config.get("general", "ps5_ip")
            port = self.config.get("general", "klog_port")
            
            if not ip:
                time.sleep(2)
                continue
            
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(20)
                s.connect((ip, port))
                Logger.log(f"Connected to KLOG at {ip}:{port}")
                
                if not self.current_title_id:
                    self._update_state("NPXS40002")
                
                buffer = ""
                last_packet = time.time()
                
                while self.running:
                    try:
                        data = s.recv(4096).decode("utf-8", errors="ignore")
                        if not data: break
                        buffer += data
                        last_packet = time.time()

                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            self._process_log_line(line)
                        
                        if time.time() - last_packet > 120 and self.current_title_id:
                            self.current_title_id = None
                            self._notify("Idle", None)
                            
                    except socket.timeout:
                        continue
            except Exception as e:
                self._notify("Offline", None)
                self.current_title_id = None
                time.sleep(10)
            finally:
                try: s.close()
                except: pass

    def _process_log_line(self, line):
        new_id = None

        proh_match = PROHIBITION_PATTERN.search(line)
        if proh_match:
            new_id = proh_match.group(1)

        if not new_id:
            scene_match = SCENE_PATTERN.search(line)
            if scene_match:
                source = scene_match.group(1)
                destination = scene_match.group(2)
                
                # Ignore internal overlay transitions
                if "FocusCapture" in destination or "ReactModalScene" in destination:
                    return 

                if "id_debug_settings" in destination:
                    new_id = "DEBUG_SETTINGS"
                else:
                    id_match = ID_EXTRACTOR.search(destination)
                    if id_match: new_id = id_match.group(1)

                if not new_id and ("AppScreen" in destination or "ApplicationScreenScene" in destination):
                    id_match_src = ID_EXTRACTOR.search(source)
                    if id_match_src: new_id = id_match_src.group(1)

        if not new_id:
            if "Unload" in line: return
            
            id_match = ID_EXTRACTOR.search(line)
            if id_match:
                found = id_match.group(1)
                if found in IGNORED_IDS: return 
                if found.startswith("NPXS") or found.startswith("CUSA") or found.startswith("PPSA"):
                     if found != self.current_title_id:
                         new_id = found
            
            if DEBUG_PATTERN.search(line):
                new_id = "DEBUG_SETTINGS"

        if new_id and new_id != self.current_title_id:
            if new_id in IGNORED_IDS: return
            Logger.log(f"Transition detected: {new_id}")
            self._update_state(new_id)

    def _update_state(self, title_id):
        self.current_title_id = title_id
        
        is_system = title_id.startswith("NPXS") or title_id == "DEBUG_SETTINGS" or title_id == "ITEM00001"
        status = "Online" if is_system else "Playing"

        # === GAME TIME LOGIC ===
        timestamp_to_send = int(time.time())

        if status == "Playing":
            # If returning to the same game session from menu
            if title_id == self.active_game_id and self.active_game_start_time:
                timestamp_to_send = self.active_game_start_time
            else:
                # New game session
                self.active_game_id = title_id
                self.active_game_start_time = timestamp_to_send
        
        # Prepare Info
        if title_id == "DEBUG_SETTINGS":
            info = SYSTEM_TITLES["DEBUG_SETTINGS"].copy()
        elif title_id in SYSTEM_TITLES:
            info = SYSTEM_TITLES[title_id].copy()
        else:
            info = self._get_game_info(title_id).copy()
        
        info["title_id"] = title_id
        info["start_timestamp"] = timestamp_to_send 
        
        self._notify(status, info)

    def _notify(self, status=None, game_info=None):
        if status is not None: self.last_status = status
        if game_info is not None: self.last_game_info = game_info
            
        full_data = {
            "status": self.last_status,
            "game": self.last_game_info,
            "stats": self.current_stats
        }
        self.callback_update(full_data)

    def _get_game_info(self, title_id):
        if title_id in self.game_cache: return self.game_cache[title_id]
        
        if title_id.startswith("NPXS"):
            return {"name": "System App", "image": "ps5", "background": ""}

        data = self._fetch_online(title_id)
        if data:
            self.game_cache[title_id] = data
            save_cache(self.game_cache)
            return data
        
        return {"name": f"Unknown ({title_id})", "image": "ps5", "background": ""}

    def _fetch_online(self, title_id):
        ps4_prefixes = ("CUSA", "CUSJ", "CUSK", "CUSC", "CUSH", "CUSE", "PLAS", "PLJM", "PCJS")
        base_url = "https://orbispatches.com" if title_id.startswith(ps4_prefixes) else "https://prosperopatches.com"
        url = f"{base_url}/{title_id}"

        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Accept-Encoding': 'gzip, deflate'
        }

        try:
            with httpx.Client(timeout=10, headers=headers, follow_redirects=True) as client:
                r = client.get(url)
                if r.status_code != 200: return None

                soup = BeautifulSoup(r.text, 'html.parser')
                name = None
                
                h1 = soup.select_one("h1.bd-title")
                if h1: name = h1.get_text(strip=True)
                
                if not name: 
                    t = soup.find('title')
                    if t and 'Patches' in t.get_text():
                        name = t.get_text(strip=True).split(' - ')[0]

                img_url = "ps5"
                bg_url = ""
                
                icon_div = soup.select_one("div.game-icon.secondary")
                if icon_div and "style" in icon_div.attrs:
                    match = re.search(r'url\((?:&quot;|")?(.*?)(?:&quot;|")?\)', icon_div["style"])
                    if match: 
                        u = match.group(1)
                        img_url = base_url + u if u.startswith("/") else u
                        bg_url = img_url

                if not name: return None
                return {"name": name, "image": img_url, "background": bg_url}

        except Exception as e:
            Logger.log(f"Scraping error {title_id}: {e}")
            return None