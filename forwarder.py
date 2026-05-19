import socketio
import requests

SERVER = "https://sonde.kushal-kc.com.np/api/injest"
API_KEY = ""

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
        print("Forwarded:", data.get("id"), data.get("lat"), data.get("lon"))
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
    'http://0.0.0.0:5000',
    namespaces=['/update_status']
)

sio.wait()