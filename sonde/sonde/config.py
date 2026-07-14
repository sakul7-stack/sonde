import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _env(key, default=""):
    return os.environ.get(key, default)


# ── Environment ──────────────────────────────────────────
DEBUG = _env("DJANGO_DEBUG", "True").lower() in ("true", "1", "yes")

# ── URLs ─────────────────────────────────────────────────
# In templates use {{ SITE_BASE_URL }} for the full host (e.g. http://127.0.0.1:8000)
if DEBUG:
    SITE_BASE_URL = _env("SITE_BASE_URL", "http://127.0.0.1:8000")
else:
    SITE_BASE_URL = _env("SITE_BASE_URL", "https://sonde.kushal-kc.com.np")

# API endpoints used by the frontend JavaScript
API_SONDES_URL  = f"{SITE_BASE_URL}/api/sondes/"
API_PRED_URL    = f"{SITE_BASE_URL}/api/pred/"
PREDICT_PROX_URL = _env("TAWHIRI_API_URL", f"{SITE_BASE_URL}/predict_prox")
DATA_SKEW_T_URL = f"{SITE_BASE_URL}/data/skewt/"
DATA_HODO_URL   = f"{SITE_BASE_URL}/data/hodograph/"
DATA_ATMOS_URL  = f"{SITE_BASE_URL}/data/atmosphere/"

# ── External services ────────────────────────────────────
SONDE_SOURCE_URL = _env("SONDE_SOURCE_URL", "http://192.168.1.15:5000")
CESIUM_TOKEN = _env("CESIUM_TOKEN", "")

# ── Secrets (for forwarder.py etc.) ─────────────────────
API_KEY = _env("API_KEY", "")
INGEST_URL = _env("INGEST_URL", f"{SITE_BASE_URL}/api/ingest/")
