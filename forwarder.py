import os
import socketio
import requests
from pathlib import Path

# Load .env from sonde/ directory
_env_path = Path(__file__).resolve().parent / "sonde" / ".env"
if _env_path.exists():
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#"):
                continue
            if "=" in _line:
                _key, _, _val = _line.partition("=")
                os.environ.setdefault(_key.strip(), _val.strip())

SERVER = os.environ.get("INGEST_URL", "https://sonde.kushal-kc.com.np/api/ingest/")
API_KEY = os.environ.get("API_KEY", "")
SONDE_SOURCE_URL = os.environ.get("SONDE_SOURCE_URL", "http://192.168.1.15:5000")

sio = socketio.Client()

@sio.on('connect', namespace='/update_status')
def on_connect():
    print("Connected to Sonde source")

@sio.on('disconnect', namespace='/update_status')
def on_disconnect():
    print("isconnected")

# TELEMETRY EVENT
@sio.on('telemetry_event', namespace='/update_status')
def on_data(data):
    try:
        requests.post(
            SERVER,
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=2
        )
        print("📡 Forwarded:", data.get("id"), data.get("lat"), data.get("lon"))
    except Exception as e:
        print("Failed:", e)

#debug
@sio.on('scan_event', namespace='/update_status')
def on_scan(data):
    print("SCAN:", data)

@sio.on('log_event', namespace='/update_status')
def on_log(data):
    print("LOG:", data)

#CONNECT
sio.connect(
    SONDE_SOURCE_URL,
    namespaces=['/update_status']
)

sio.wait()