# PS5 Discord Rich Presence Client

![logo](https://i.imgur.com/1wxxHoq.png)

A custom Python application that monitors PlayStation 5 gameplay through
klog logs and updates Discord Rich Presence automatically.\
This application features a full GUI built with **CustomTkinter**,
online game title lookup, caching, system tray integration,
multi‑language support, and automatic reconnecting.

------------------------------------------------------------------------

## 🚀 Features

-   **Discord Rich Presence Integration**
-   ![image](https://i.imgur.com/5sKIRNp.png)
    -   Shows currently played PS5/PS4 game
    -   Auto‑updates with game icons and names
-   **Real‑time PS5 Monitoring**
    -   Connects to klog service (port 9081)
    -   Detects title IDs from logstream
-   **Multi‑language Support**
-   **Game Title & Icon Web Scraping**
    -   PS4 titles → `orbispatches.com`
    -   PS5 titles → `prosperopatches.com`
-   **Cache System for Fast Lookups**
-   **CustomTkinter GUI**
-   **System Tray Support (pystray)**
-   **Auto Reconnect**
-   **Config Save/Load**
-   **Beautiful Logging Console**

------------------------------------------------------------------------

## 📦 Requirements

This project uses:

-   Python 3.10+
-   `customtkinter`
-   `pypresence`
-   `requests`
-   `pystray`
-   `Pillow`
-   `beautifulsoup4`
-   `pypandoc`

Install all dependencies:

``` sh
pip install customtkinter pypresence requests pystray pillow beautifulsoup4 pypandoc
```

------------------------------------------------------------------------

## ⚙️ How It Works

1.  Create a **Discord Application** at\
    https://discord.com/developers/applications/

    -   Copy the **Application ID** (also called *Client ID*)\
    -   Paste it into the app's **Discord Client ID** field\

2.  The app connects to your PS5's **klog service** on port **9081**.

3.  When you start a game, the PS5 klog outputs a line containing a
    **title_id**\
    (e.g., `PPSA12345` or `CUSA12345`).

4.  The application extracts the title ID and:

    -   Looks it up in the local cache\
    -   If not cached, fetches game info and icons from the web

5.  Discord Rich Presence is updated with:

    -   Game name\
    -   Game artwork\
    -   Time playing\
    -   System icon

6.  The GUI shows:

    -   Connection status\
    -   Current game\
    -   Logs of all operations


------------------------------------------------------------------------

## 🖼️ GUI Overview
![image](https://i.imgur.com/ZtS6Rox.png)

-   **IP Address Field** → your PS5's LAN IP\
-   **Discord Client ID** → from the Discord Developer Portal\
-   **Language Selection**\
-   **Log Output**\
-   **Status Panel**\
-   **Tray Icon Options**

------------------------------------------------------------------------

## 🔧 Configuration Files

  File               Purpose
  ------------------ ------------------------------------
  `config.json`      Stores PS5 IP, Client ID, language
  `ps5_cache.json`   Cached game info (fast lookups)
  `languages.json`   Language definitions
  `icon.ico`         App icon

------------------------------------------------------------------------

## 📝 Web Scraping Behavior

### For PS4 titles

Prefixes: `CUSA`, `CUSJ`, `CUSK`, etc.\
Scraped from: **https://orbispatches.com**

### For PS5 titles

Scraped from: **https://prosperopatches.com**

Fallback name resolution: 1. `<h1 class="bd-title">` 2. Image alt text
3. Page title 4. Title ID (fallback)

------------------------------------------------------------------------

## 🖥️ Running the Application

Download the .EXE file from the [releases](https://github.com/MestreTM/PS5-Discord-RPC/releases) and run it.

or

Clone the repository and run:

``` sh
python app.py
```

Make sure: - Your PS5 is in **Debug Settings → klog enabled** - You know
the PS5 local IP - Discord is running - Your Discord application has
uploaded a PS5 logo as an asset

------------------------------------------------------------------------

## 📂 Building as EXE (optional)

This project supports PyInstaller packaging:

``` sh
pyinstaller --noconsole --onefile --clean --name "PS5 Discord RPC" --icon=icon.ico --add-data "icon.ico;." --collect-all customtkinter app.py 
```
