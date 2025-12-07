# PS5 Monitor Hub
![logo](https://i.imgur.com/mSmB4f3.png)

**PS5 status monitor and integration hub.** Displays
real-time game activity via **Discord Rich Presence (KLOG/EtaHen)** and
features a modular **Plugin System** for custom IoT, Home Assistant, and
monitoring integrations.

### ⚠️ Warning: For temperature and frequency statuses in HAOS, install [AirPSX](https://github.com/barisyild/airpsx/) and activate on your PS5 JB.

------------------------------------------------------------------------

## 🚀 Key Features

-   **Modular Architecture:** Extend functionality using Python plugins
    (e.g., web dashboard, session logger).
-   **Discord Rich Presence:** Shows current game, artwork, and session
    time.
-   **Home Assistant (MQTT) Integration:** Exports status, game details,
    and hardware telemetry.
-   **Real-time PS5 Monitoring:** Connects to KLOG (port 9081) for
    instant Title ID detection.
-   **Hardware Telemetry:** Scrapes internal PS5 debug stats such as
    CPU/SoC temperature and frequency.
-   **Game Data & Caching:** Fetches game data and artwork with local
    caching.
-   **CustomTkinter GUI:** Clean modern UI with system tray support.
-   **Auto Reconnect:** Robust connection and recovery mechanisms.

![image](https://i.imgur.com/5sKIRNp.png)![image](https://i.imgur.com/z91yWhq.png)
------------------------------------------------------------------------

## ⚙️ Requirements & Installation

This project uses asynchronous libraries and requires specific tools for
stats monitoring.

### 📦 Dependencies

Install all dependencies:

``` bash
pip install -r requirements.txt
```

Or manually:

    customtkinter
    pystray
    Pillow
    pypresence
    paho-mqtt
    playwright
    beautifulsoup4
    httpx
    requests

### 🌐 Playwright Browser Setup

Required for hardware stats scraping:

``` bash
playwright install chromium
```

------------------------------------------------------------------------

## 🔌 How It Works (Hub Architecture)

### Monitor Core

-   Connects to PS5 KLOG (Title ID detection)
-   Connects to PS5 debug server for hardware stats

### Event Broadcast

-   Any status change triggers the `on_core_update` event.

### Handlers

-   **DiscordHandler** updates Discord Rich Presence.
-   **HAOSHandler** publishes MQTT telemetry.
-   **Plugins** receive real-time data automatically.

### Components Overview

  -----------------------------------------------------------------------
| Component       | Port / Destination | Purpose                                      |
|-----------------|--------------------|----------------------------------------------|
| KLOG Monitor    | 9081               | Detects Title ID & power state               |
| Stats Monitor   | 1214               | Reads hardware telemetry                     |
| Game Scraping   | Web scraping       | Fetches covers & titles from patch servers   |

------------------------------------------------------------------------

## 🛠️ Configuration & Running

### **🔽 EXE Build Available**

A pre-built **PyInstaller EXE** is available in the **[Releases](https://github.com/MestreTM/PS5-Monitor-Hub/releases)** section
of the repository for easy run.

### 1. Initial Setup

-   Create a Discord application and obtain Client ID.
-   Ensure your PS5 has a static LAN IP.
-   Create a `plugins` folder for custom modules.

### 2. Running

``` bash
python main.py
```

Headless mode:

``` bash
python main.py --nogui
```

### 3. Hot Reload

Reload plugins instantly through the GUI.

------------------------------------------------------------------------

## 🖼️ GUI Overview

-   **General Tab:** PS5 IP settings, plugin reload, global logs.
-   **Discord / Home Assistant Tabs:** Dedicated configuration panels.
-   **Dynamic Plugin Tabs:** Automatically created per plugin.

------------------------------------------------------------------------

## 📂 Configuration Files

  File                    Purpose
  ----------------------- --------------------------------------
  `config.json`           User settings & plugin configuration
  `ps5_game_cache.json`   Cached game metadata

------------------------------------------------------------------------

## 📦 Building as EXE (optional)

``` bash
pyinstaller --noconsole --onefile --clean --name "PS5 Monitor Hub" --icon=icon.ico main.py
```

