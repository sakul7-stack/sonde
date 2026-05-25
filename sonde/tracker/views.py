from django.http import JsonResponse,HttpResponse,response
from django.views.decorators.csrf import csrf_exempt
from .models import Sonde, Telemetry, Prediction
import json
from datetime import datetime
from django.shortcuts import render
import math
import requests
from accounts.models import APIKey
import threading

def check_key(request):
    key = request.headers.get("X-API-KEY")

    if not key:
        return None

    try:
        return APIKey.objects.select_related("user").get(key=key)
    except APIKey.DoesNotExist:
        return None


def parse_time(t):
    return datetime.fromisoformat(t.replace('Z', '+00:00'))

def fetch_and_store_prediction(sonde, telemetry):
    """Call Tawhiri once and store raw JSON."""
    if Prediction.objects.filter(sonde=sonde).exists():
        return  # already have one, skip

    dt_str = telemetry.datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
    params = {
        "profile": "standard_profile",
        "pred_type": "single",
        "launch_datetime": dt_str,
        "launch_latitude": telemetry.lat,
        "launch_longitude": telemetry.lon,
        "launch_altitude": telemetry.alt,
        "ascent_rate": 5,
        "burst_altitude": 30000,
        "descent_rate": 5,
    }
    try:
        resp = requests.get("https://api.v2.sondehub.org/tawhiri", params=params, timeout=10)
        resp.raise_for_status()
        Prediction.objects.create(sonde=sonde, raw=resp.json())
    except Exception as e:
        print(f"Prediction fetch failed: {e}")




@csrf_exempt
def ingest(request):
    if request.method != "POST":
        return JsonResponse({"error": "POST only"}, status=405)

    api_obj = check_key(request)

    if not api_obj:
        return JsonResponse({"error": "unauthorized"}, status=403)


    try:
        data = json.loads(request.body)

        # ---- SONDE ----
        sonde,_ = Sonde.objects.get_or_create(
            sonde_id=data["id"],
            defaults={
                "type": data.get("type"),
                "subtype": data.get("subtype"),
                "frequency": data.get("freq")
            }
        )

        # ---- TELEMETRY ----
        telemetry = Telemetry.objects.create(
            sonde=sonde,
            frame=data.get("frame"),
            datetime=parse_time(data["datetime"]),

            lat=data.get("lat"),
            lon=data.get("lon"),
            alt=data.get("alt"),

            vel_h=data.get("vel_h"),
            vel_v=data.get("vel_v"),
            heading=data.get("heading"),

            temp=data.get("temp"),
            humidity=data.get("humidity"),
            pressure=data.get("pressure"),

            battery=data.get("batt"),

            f_centre=data.get("f_centre"),
            snr=data.get("snr"),

            raw=data  
        )
        threading.Thread(
            target=fetch_and_store_prediction,
            args=(sonde, telemetry),
            daemon=True
            ).start()

        return JsonResponse({"ok": True})

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)
    
from django.http import JsonResponse

def sondes(request):
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)
    
    sonde = Sonde.objects.order_by('-date').first()

    if not sonde:
        return JsonResponse({"data": []})

    sonde_data = list(
        Telemetry.objects.filter(sonde=sonde)
        .order_by('-frame')
        .values(
            'frame', 'datetime',
            'lat', 'lon', 'alt',
            'vel_h', 'vel_v', 'heading',
            'temp', 'humidity', 'pressure',
            'battery', 'f_centre', 'snr'
        )
    )

    return JsonResponse({
        "sonde_id": sonde.sonde_id,
        "type": sonde.type,
        "subtype": sonde.subtype,
        "data": sonde_data
    })

def predict_path(request):
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)    
    sonde_id = request.GET.get('sonde_id')  
    if not sonde_id:
        return JsonResponse({"error": "sonde_id required"}, status=400)
    
    pred = Prediction.objects.filter(sonde__sonde_id=sonde_id).first()  
    if not pred:
        return JsonResponse({"error": "not found"}, status=404)
    
    return JsonResponse({
        'sonde': sonde_id,
        'date': pred.created_at,  
        'data': pred.raw
    })



def home(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'home.html')

def view_3d(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'3d.html')

def api_doc(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'api.html')

def faq(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'faq.html')


def predict(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'predict.html')



def predict_prox(request):
    base_url = "https://api.v2.sondehub.org/tawhiri"

    # forward query parameters from frontend
    params = request.GET.dict()

    try:
        r = requests.get(base_url, params=params, timeout=30)
        data = r.json()
        return JsonResponse(data, safe=False)

    except Exception as e:
        return JsonResponse({
            "error": str(e)
        }, status=500)

def burst(request):
    if request.method != 'GET':
        return HttpResponse('only get')
    
    return render(request,'burst.html')



def skewt_page(request):
    return render(request, 'skewt.html')

ASCENT_RATE = 5.0      # m/s
DESCENT_RATE = -5.0    # m/s
BURST_ALT = 30000      # meters
DT = 60                # seconds per step
STEPS = 60             # prediction length


