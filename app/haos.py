import json
import threading
import time
import paho.mqtt.client as mqtt
from .utils import ConfigManager, Logger

class HAOSHandler:
    def __init__(self):
        self.config = ConfigManager()
        self.client = None
        self.connected = False
        self.running = False
        self.last_payload = None

    def connect(self):
        """Starts MQTT connection in a separate thread."""
        if not self.config.get("haos", "enabled"):
            return

        broker = self.config.get("haos", "mqtt_broker")
        if not broker:
            Logger.log("HAOS: Broker IP not configured.")
            return

        if self.client:
            return  # Already connected

        self.running = True
        threading.Thread(target=self._run_mqtt, daemon=True).start()

    def disconnect(self):
        """Cleanly disconnects MQTT."""
        self.running = False
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except:
                pass
            self.client = None
            self.connected = False
            Logger.log("HAOS: Disconnected.")

    def _run_mqtt(self):
        """Main connection and reconnection loop."""
        broker = self.config.get("haos", "mqtt_broker")
        port = int(self.config.get("haos", "mqtt_port") or 1883)
        user = self.config.get("haos", "mqtt_user")
        password = self.config.get("haos", "mqtt_pass")

        while self.running:
            try:
                # Client Setup
                self.client = mqtt.Client(client_id="PS5_Monitor_PC", protocol=mqtt.MQTTv311)
                
                if user and password:
                    self.client.username_pw_set(user, password)

                self.client.on_connect = self._on_connect
                self.client.on_disconnect = self._on_disconnect

                Logger.log(f"HAOS: Connecting to {broker}:{port}...")
                self.client.connect(broker, port, 60)
                self.client.loop_start()

                # Keep thread alive
                while self.running and self.client:
                    time.sleep(1)

            except Exception as e:
                Logger.log(f"HAOS Error: {e}")
                self.connected = False
                if self.client:
                    self.client.loop_stop()
                    self.client = None
                
                # Wait before reconnecting
                if self.running:
                    time.sleep(10)

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            Logger.log("HAOS: Connected to Broker!")
            # Resend last state upon reconnection
            if self.last_payload:
                self._publish(self.last_payload)
        else:
            Logger.log(f"HAOS: Connection failed (Code {rc})")
            self.connected = False

    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            Logger.log("HAOS: Connection lost unexpectedly.")

    def update(self, data):
        """Receives data from Core and publishes to MQTT."""
        if not self.config.get("haos", "enabled") or not self.client or not self.connected:
            return

        try:
            status = data.get("status", "Offline")
            game = data.get("game", {})
            stats = data.get("stats", {})

            # Flatten JSON for Home Assistant
            payload = {
                "status": status,
                "game_name": game.get("name", "None"),
                "title_id": game.get("title_id", ""),
                "image": game.get("image", ""),
                "background": game.get("background", ""),
                "cpu_temp": stats.get("cpu_temp", "N/A"),
                "soc_temp": stats.get("soc_temp", "N/A"),
                "frequency": stats.get("frequency", "N/A"),
                "start_timestamp": game.get("start_timestamp", None) 
            }

            # Only publish if changed
            if payload != self.last_payload:
                self._publish(payload)
                self.last_payload = payload

        except Exception as e:
            Logger.log(f"HAOS Update Error: {e}")

    def _publish(self, payload_dict):
        topic = self.config.get("haos", "mqtt_topic")
        if not topic: return

        try:
            json_str = json.dumps(payload_dict)
            self.client.publish(topic, json_str, retain=True)
        except Exception as e:
            Logger.log(f"HAOS Publish Error: {e}")