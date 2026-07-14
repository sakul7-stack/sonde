import os
import requests
import time
import random
from datetime import datetime, timezone, timedelta
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

SERVER = os.environ.get("INGEST_URL", "http://127.0.0.1:8000/api/ingest/")
API_KEY = os.environ.get("API_KEY", "")

SONDE_ID = "test-10d"

# ---- INITIAL STATE ----
lat = 27.682
lon = 85.2881
alt = 12000

vel_h = 30.0
vel_v = 3.5
heading = 120.0

frame = 3600

start_time = datetime.now(timezone.utc)


def iso_time(t):
    return t.isoformat().replace("+00:00", "Z")


while True:
    try:
        # ---- TIME ----
        current_time = start_time + timedelta(seconds=frame - 3600)

        # ---- SIMULATE MOVEMENT ----
        lat += random.uniform(-0.0005, 0.0005)
        lon += random.uniform(0.0005, 0.0015)   # drifting east
        alt += vel_v + random.uniform(-0.5, 0.5)

        # ---- WEATHER ----
        temp = -40 - (alt / 1000) + random.uniform(-1, 1)
        humidity = max(0, random.uniform(0, 5))
        pressure = -1  # keep as is

        # ---- SIGNAL ----
        snr = round(random.uniform(5, 15), 1)
        ppm = round(random.uniform(100, 300), 1)

        # ---- VELOCITY ----
        vel_h += random.uniform(-1, 1)
        vel_v += random.uniform(-0.2, 0.2)
        heading += random.uniform(-2, 2)

        # ---- DATA PACKET ----
        data = {
            "type": "IMET5",
            "frame": frame,
            "id": SONDE_ID,

            "datetime": iso_time(current_time),

            "lat": round(lat, 5),
            "lon": round(lon, 5),
            "alt": round(alt, 1),

            "temp": round(temp, 1),
            "humidity": round(humidity, 1),
            "pressure": pressure,

            "vel_h": vel_h,
            "vel_v": vel_v,
            "heading": heading,

            "subtype": "iMet-54",
            "ref_datetime": "UTC",
            "ref_position": "MSL",
            "version": "1.8.2",

            "batt": -1,

            "freq_float": 401.999,
            "freq": "402.000 MHz",

            "sdr_device_idx": "0",
            "snr": snr,

            "fest": [-1875.0, 3000.0],
            "ppm": ppm,

            "f_centre": 401999562.5,
            "f_error": 562.5,

            "aprsid": "IMET94773"
        }

        # ---- SEND ----
        res = requests.post(
            SERVER,
            json=data,
            headers={"X-API-KEY": API_KEY},
            timeout=2
        )

        print(f"📡 Frame {frame} | Alt {data['alt']} | Lat {data['lat']} Lon {data['lon']} | SNR {snr}")

        frame += 1

        time.sleep(2)  

    except Exception as e:
        print("❌ Error:", e)
        time.sleep(2)