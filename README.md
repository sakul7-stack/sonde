# Radiosonde Tracking

A web-based radiosonde tracking platform.

**Live Site:** [sonde.kushal-kc.com.np](https://sonde.kushal-kc.com.np/)

[![Demo](demo.png)](https://sonde.kushal-kc.com.np/)

---

## About

Real-time and historical tracking of **radiosondes** which are battery-powered telemetry instruments carried into the atmosphere by weather balloons. Radiosondes measure and transmit key atmospheric parameters including:

- Temperature
- Relative Humidity
- Altitude & Pressure
- Wind Speed & Direction
- GPS Position (Latitude / Longitude)

The tracker aggregates radiosonde data useful for meteorology enthusiasts, atmospheric researchers, and amateur radio operators.

Radiosonde detection and decoding is powered by [**radiosonde_auto_rx**](https://github.com/projecthorus/radiosonde_auto_rx) — an open-source decoder that automatically detects and decodes radiosonde signals using RTL-SDR or AirSpy receivers.

---

## Features

- **Live Map View** — Real-time radiosonde positions on an interactive map, with live telemetry, predicted flight path, KML download, hodograph, and a live green/red data-freshness indicator
- **Flight Prediction** — Adjust ascent rate, burst altitude, and other parameters to generate a predicted flight path; export as CSV or KML
- **Burst Calculator** — Estimate balloon burst altitude based on fill parameters
- **3D Visualization** — Upload a KML file to view the flight path in 3D using Cesium
- **Thermodynamic Diagrams** — Skew-T, Emagram, Stüve, and Tephigram plots, plus hodographs
- **Historical Data** — Browse and filter past radiosonde flights by date or serial number, with per-flight and aggregate statistics
- **Chase Mode** — Live map of active chasers (via WebSockets) alongside sonde positions, predicted paths, and burst/landing markers
- **Sonde Recovery Reporting** — Submit a report if you find a landed radiosonde
- **API Access** — Programmatic access to sonde lists, telemetry, KML paths, Skew-T plots, and hodograph images
- **Installable PWA** — Add the tracker to your home screen (web app manifest + service worker)

---

## Pages

| URL | Description |
|-----|-------------|
| `/` | Live tracker — latest sonde positions, predicted path, KML download, hodograph, live telemetry |
| `/predict/` | Flight path predictor — adjust parameters, export CSV/KML (uses [TAWHIRI](https://github.com/cuspaceflight/tawhiri) engine) |
| `/burst/` | Balloon burst altitude calculator |
| `/3d/` | 3D flight path viewer — upload a KML file, rendered with Cesium |
| `/skewt/` | Skew-T / thermodynamic diagram viewer |
| `/history/` | Historical flight data browser with filters and stats |
| `/report/submit/` | Report a found/recovered radiosonde |
| `/chase/` | Chase mode — live chaser positions and sonde tracking (login required) |
| `/accounts/dash/` | User dashboard — register or sign in with Google to get your API key |

---

## Data Forwarding

This platform accepts radiosonde telemetry forwarded from **radiosonde_auto_rx** stations. If you run a receiver, you can contribute data to this site.

### Requirements

```
pip install python-socketio requests
```

### Steps

1. Run `radiosonde_auto_rx` on your receiver station (default web interface at `http://0.0.0.0:5000`)
2. Register at [sonde.kushal-kc.com.np/accounts/dash/](https://sonde.kushal-kc.com.np/accounts/dash/) via Google or email to get your API key
3. Edit `forwarder.py` with your settings and run it

### forwarder.py

Edit the following values directly in `forwarder.py`:

- `SERVER` — server ingest endpoint
- `API_KEY` — your API key from the dashboard
- `SONDE_SOURCE_URL` — your local `radiosonde_auto_rx` web interface

```python
import socketio
import requests

SERVER = "https://sonde.kushal-kc.com.np/api/ingest/"
API_KEY = "YOUR_API_KEY_HERE"
SONDE_SOURCE_URL = "http://192.168.1.15:5000"

sio = socketio.Client()

@sio.on('connect', namespace='/update_status')
def on_connect():
    print("Connected to Sonde source")

@sio.on('disconnect', namespace='/update_status')
def on_disconnect():
    print("Disconnected")

@sio.on('telemetry_event', namespace='/update_status')
def on_data(data):
    try:
        requests.post(
            SERVER,
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=2
        )
        print("Forwarded:", data.get("id"), data.get("lat"), data.get("lon"))
    except Exception as e:
        print("Failed:", e)

sio.connect(SONDE_SOURCE_URL, namespaces=['/update_status'])
sio.wait()
```

> The forwarder connects to your local `radiosonde_auto_rx` web interface and streams telemetry events to the Sonde server in real time. Make sure `auto_rx` is running before starting the forwarder.

---

## API Documentation

**Base URL:** `https://sonde.kushal-kc.com.np`

### Authentication

Include your API key in the request headers:

```
X-API-KEY: YOUR_API_KEY
```

Get your API key from the [dashboard](https://sonde.kushal-kc.com.np/accounts/dash/) after registering.

> There is no rate limit on the API — please use it responsibly.

---

### 1. Get Sonde List by Date

```
GET /data/data_by_date/?date=YYYY-MM-DD
```

Returns a list of sondes active on a given date. **Requires API key.**

**curl:**
```bash
curl "https://sonde.kushal-kc.com.np/data/data_by_date/?date=2026-05-04" \
  -H "X-API-KEY: YOUR_KEY"
```

**Python:**
```python
import requests

url = "https://sonde.kushal-kc.com.np/data/data_by_date/"
headers = {"X-API-KEY": "YOUR_KEY"}
params = {"date": "2026-05-04"}

r = requests.get(url, headers=headers, params=params)
print(r.json())
```

---

### 2. Get Sonde Telemetry

```
GET /data/sonde_data/?sonde_id=ID
```

Returns full telemetry data for a given sonde. **Requires API key.**

**curl:**
```bash
curl "https://sonde.kushal-kc.com.np/data/sonde_data/?sonde_id=IMET5-55095407" \
  -H "X-API-KEY: YOUR_KEY"
```

**Python:**
```python
import requests

url = "https://sonde.kushal-kc.com.np/data/sonde_data/"
headers = {"X-API-KEY": "YOUR_KEY"}
params = {"sonde_id": "IMET5-55095407"}

r = requests.get(url, headers=headers, params=params)
print(r.json())
```

---

### 3. Download KML Path

```
GET /data/sonde_KML/?sonde_id=ID
```

Downloads the flight path as a `.kml` file. **Requires API key.**

**curl:**
```bash
curl "https://sonde.kushal-kc.com.np/data/sonde_KML/?sonde_id=IMET5-55095407" \
  -H "X-API-KEY: YOUR_KEY" \
  -o sonde.kml
```

**Python:**
```python
import requests

url = "https://sonde.kushal-kc.com.np/data/sonde_KML/"
headers = {"X-API-KEY": "YOUR_KEY"}
params = {"sonde_id": "IMET5-55095407"}

r = requests.get(url, headers=headers, params=params)
with open("sonde.kml", "wb") as f:
    f.write(r.content)
```

---

### 4. Thermodynamic Diagrams

Return meteorological plot images. **No API key required.**

```
GET /data/skewt/?sonde_id=ID       # Skew-T log-P diagram
GET /data/emagram/?sonde_id=ID     # Emagram
GET /data/stuve/?sonde_id=ID       # Stüve diagram
GET /data/tephigram/?sonde_id=ID   # Tephigram
```

```
https://sonde.kushal-kc.com.np/data/skewt/?sonde_id=IMET5-55093438
```

---

### 5. Hodograph

```
GET /data/hodograph/?sonde_id=ID
```

Returns a hodograph (wind profile) image. **No API key required.**

```
https://sonde.kushal-kc.com.np/data/hodograph/?sonde_id=IMET5-55093438
```

---

### 6. Atmosphere JSON

```
GET /data/atmosphere/?sonde_id=ID
```

Returns derived atmospheric quantities (pressure, dewpoint, potential temperature, CAPE/CIN, etc.) as JSON. **No API key required.**

---

### API Key Requirement Summary

| Endpoint | Auth Required |
|----------|:---:|
| `/data/data_by_date/` | Yes |
| `/data/sonde_data/` | Yes |
| `/data/sonde_KML/` | Yes |
| `/data/skewt/` | No |
| `/data/emagram/` | No |
| `/data/stuve/` | No |
| `/data/tephigram/` | No |
| `/data/hodograph/` | No |
| `/data/atmosphere/` | No |

---

## Acknowledgements

- [projecthorus/radiosonde_auto_rx](https://github.com/projecthorus/radiosonde_auto_rx) — open-source radiosonde decoder and auto-tracking software
- [TAWHIRI](https://github.com/cuspaceflight/tawhiri) — flight prediction engine used for trajectory forecasting
- [CesiumJS](https://cesium.com/) — 3D globe rendering for flight path visualization

---

## License

This project is open source under the [MIT License](LICENSE).
