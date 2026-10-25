# Sydney Trains Kindle Departure Board 🚆

**Real-Time Sydney & NSW TrainLink Departure Indicator for Kindle Paperwhite**

Directly ported from the ESP32 E-Ink **TransportTracker** firmware (`dataFetcher.cpp` & `displayManager.cpp`), this application transforms an Amazon Kindle Paperwhite into a live railway station departure board.

![Kindle Paperwhite Compatible](https://img.shields.io/badge/Kindle-Paperwhite%201%20(5.6.1.1)-black?style=flat-square)
![Dependencies](https://img.shields.io/badge/Dependencies-Standard%20Library%20Only-blue?style=flat-square)
![Stations Supported](https://img.shields.io/badge/Stations-351%20NSW%20Stations-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## Features

- **Hero Departure Card**:
  - Live departure countdown pill (`in 4 MINS`, `NOW DEPARTING`).
  - Line code badge (e.g. **T1**, **T2**, **T4**, **T9**, **CCN**, **BMT**).
  - Platform assignment (`PLATFORM 1`).
  - Service metadata: Car length (e.g., `8 Cars`) and live carriage occupancy (`Many Seats Available`, `Standing Room Only`).
  - Departure and arrival clock times with travel duration.
- **Upcoming Departures Board**: Dynamic table listing the next 3–4 scheduled or real-time train services.
- **One-Tap Route Reversal**: Tap `[ ⇄ SWAP ROUTE ]` on the Kindle touch screen to instantly flip your commute (e.g., *Penrith &rarr; Central* becomes *Central &rarr; Penrith*).
- **All 351 NSW Railway Stations**: Pre-indexed station codes (`stations.json`) covering the entire Sydney suburban network and NSW TrainLink intercity corridors.
- **Automatic Sydney Daylight Savings (AEDT / AEST)**: Pure Python DST rule calculation without needing `tzdata` or external packages.
- **Strict ES5 Browser Compatibility**: Handcrafted vanilla ES5 JavaScript engineered for Kindle Paperwhite 1's legacy WebKit browser (`FW 5.6.1.1`).
- **Zero External Dependencies**: Pure Python 3 standard library server (`http.server`, `urllib`, `json`). No `pip install` required.

---

## Quick Start (Standalone Mode)

### 1. Clone & Configure
```bash
git clone https://github.com/Elliot-Mason/Kindle-sydney-trains.git
cd Kindle-sydney-trains

# Copy example configuration
cp config.example.json config.json
```

Edit `config.json` with your desired origin and destination station codes:
```json
{
  "origin_code": "10101252",
  "origin_name": "Penrith",
  "destination_code": "10101100",
  "destination_name": "Central",
  "poll_interval_ms": 30000,
  "port": 5052
}
```
*(Station codes can be found in `stations.json`)*.

### 2. Run the Server
```bash
python server.py
```
The server outputs your local network IP (e.g., `http://192.168.1.100:5052/kindle`).

### 3. Open on Kindle Paperwhite
1. Connect your Kindle to your Wi-Fi network.
2. Tap the **Menu (&vellip;)** in the top right corner &rarr; **Experimental Web Browser**.
3. Type: `http://<YOUR_PC_IP>:5052/kindle`
4. Bookmark the URL for instant 1-tap launching.

---

## Running in Kindle Simulator

You can run this app inside the [Kindle Paperwhite Simulator](https://github.com/Elliot-Mason/Kindle-simulator):

### Option A: Via `--app` argument
```bash
cd ../Kindle-simulator
python server.py --app ../Kindle-sydney-trains
```

### Option B: Auto-Discovery Folder
Drop or symlink this directory into the simulator's `apps/` directory:
```bash
Kindle-simulator/
  └── apps/
      └── train/         <-- Drop Kindle-sydney-trains here
```
The simulator will automatically discover it, register the backend routes, and mount it to the multi-app switcher.

---

## Running Natively on a Jailbroken Kindle (No PC Needed)

You can run this departure board directly on your Kindle with **zero external PC or server running**. The Kindle will connect to Wi-Fi, fetch train departures from Transport for NSW, and render them on-device.

### Prerequisites
1. **Jailbroken Kindle Paperwhite 1** (FW 5.6.1.1 or similar).
2. **KUAL** (Kindle Unified Application Launcher) installed.
3. **Python 3** installed on Kindle (install NiLuJe's `python3` package via MRPI or KUAL from the MobileRead forum).

### Installation Steps
1. Connect your Kindle to your computer via USB.
2. Copy this entire folder into the Kindle's `extensions` directory:
   ```
   [Kindle USB Root]
     └── extensions/
         └── sydney-trains/        <-- Copy this repo here
             ├── config.xml
             ├── menu.json
             ├── bin/launcher.sh
             ├── server.py
             ├── kindle.html
             ├── stations.json
             └── config.json       (copy from config.example.json)
   ```
3. Copy `config.example.json` to `config.json` inside that folder and set your origin/destination station codes.
4. Safely eject and unplug the USB cable.

### Launching on the Kindle
1. On your Kindle home screen, tap **KUAL**.
2. Select **Sydney Trains Indicator** &rarr; tap **Start (Standalone On-Device)**.
3. The launcher will automatically:
   - Prevent screensaver/sleep timeout (`preventScreenSaver = 1`).
   - Launch `python3 server.py` in the background on `127.0.0.1:5052`.
   - Open the Kindle Experimental Browser directly to `http://127.0.0.1:5052/kindle`.
4. Your departure board will now update live every 30 seconds completely standalone!

### Stopping the App
Open **KUAL** &rarr; **Sydney Trains Indicator** &rarr; **Stop App & Re-enable Sleep**.

---

## Architecture

```
Kindle-sydney-trains/
├── config.xml              # KUAL extension manifest for jailbroken Kindle
├── menu.json               # KUAL on-device menu definition
├── bin/
│   └── launcher.sh         # On-device background daemon & browser launcher
├── kindle-app.json         # Plugin manifest for Kindle-simulator
├── kindle.html             # High-contrast ES5 Sydney Trains indicator board
├── server.py               # Transport for NSW departure parser & pure Python DST engine
├── stations.json           # All 351 Sydney & NSW TrainLink station codes
├── config.example.json     # Configuration template
├── .gitignore              # Ignores local user config and caches
└── README.md
```

## License

MIT License.
