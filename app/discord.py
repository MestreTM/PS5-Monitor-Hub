from pypresence import Presence
import time
import threading
from .utils import ConfigManager, Logger

class DiscordHandler:
    def __init__(self):
        self.config = ConfigManager()
        self.rpc = None
        self.last_game_id = None
        self.last_timestamp = None
        self.lock = threading.Lock() # Prevents overlapping updates

    def connect(self):
        if not self.config.get("discord", "enabled"): return
        client_id = self.config.get("discord", "client_id")
        
        if not client_id:
            Logger.log("Discord Client ID not configured.")
            return

        try:
            if not self.rpc:
                self.rpc = Presence(client_id)
                self.rpc.connect()
                Logger.log("Discord RPC Connected.")
        except Exception as e:
            Logger.log(f"Error connecting to Discord: {e}")

    def disconnect(self):
        with self.lock:
            if self.rpc:
                try: 
                    self.rpc.clear()
                    self.rpc.close()
                except: pass
                self.rpc = None
                self.last_game_id = None
                Logger.log("Discord RPC Disconnected.")

    def update(self, data):
        """
        Starts the update in a separate thread to avoid 'Event Loop' conflicts
        with Playwright running in the main Core thread.
        """
        threading.Thread(target=self._update_thread, args=(data,), daemon=True).start()

    def _update_thread(self, data):
        with self.lock:
            if not self.config.get("discord", "enabled"):
                if self.rpc: self.disconnect()
                return

            # Try to connect if not connected
            if not self.rpc: 
                # We call connect directly here (without the lock, as connect handles itself or is simple)
                # But to be safe, we are already inside the lock.
                # However, connect() is not calling 'update', so it's fine.
                try:
                    client_id = self.config.get("discord", "client_id")
                    if client_id:
                        self.rpc = Presence(client_id)
                        self.rpc.connect()
                        Logger.log("Discord RPC Connected.")
                    else:
                        return
                except Exception as e:
                    # Silent fail to avoid spamming logs if Discord is closed
                    return

            if not self.rpc: return

            status = data.get("status")
            game = data.get("game", {})
            title_id = game.get("title_id")
            
            # Use the timestamp calculated by Core to preserve session time
            start_timestamp = game.get("start_timestamp", int(time.time()))

            try:
                if status in ["Playing", "Online"] and game:
                    
                    # Avoid duplicate updates if nothing changed
                    if self.last_game_id == title_id and self.last_timestamp == start_timestamp:
                        return
                    
                    self.last_game_id = title_id
                    self.last_timestamp = start_timestamp

                    img = game.get("image", "ps5")
                    if not img or not img.startswith("http"): img = "ps5"

                    state_text = game.get("name", "Unknown")
                    details_text = "In Main Menu" if status == "Online" else "Playing on PS5"
                    
                    if title_id == "NPXS40008": details_text = "System Settings"
                    if title_id == "DEBUG_SETTINGS": details_text = "Debug / Toolbox"

                    self.rpc.update(
                        state=state_text,
                        details=details_text,
                        large_image=img,
                        large_text=state_text,
                        small_image="ps5",
                        small_text="PS5",
                        start=start_timestamp
                    )
                    Logger.log(f"Discord updated: {state_text}")

                elif status in ["Idle", "Offline"]:
                    if self.last_game_id is not None:
                        self.rpc.clear()
                        self.last_game_id = None

            except Exception as e:
                Logger.log(f"Error updating Discord: {e}")
                # If connection is lost, force reconnection next time
                try:
                    self.rpc.close()
                except: pass
                self.rpc = None