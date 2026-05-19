from django.shortcuts import render
from tracker.models import Sonde,Telemetry
from accounts.models import Profile,APIKey,ContributorInfo
from django.http import JsonResponse,HttpResponse
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
import math
from io import BytesIO

def estimate_pressure(alt_m, temp_c, humidity_pct):
    if humidity_pct <= 0:
        humidity_pct = 1  
    T = temp_c + 273.15
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    e = (humidity_pct / 100.0) * es
    Tv = T / (1 - (e / 1013.25) * (1 - 0.622))
    g = 9.80665
    R = 287.05
    P0 = 1013.25
    H = (R * Tv) / g
    return P0 * math.exp(-alt_m / H)

def dewpoint(temp_c, humidity_pct):
    if humidity_pct <= 0:
        return temp_c - 30  # fallback
    a, b = 17.67, 243.5
    gamma = math.log(humidity_pct / 100.0) + (a * temp_c) / (b + temp_c)
    return (b * gamma) / (a - gamma)

def skewt(request):
    if request.method != 'GET':
        return HttpResponse('GET only')

    sonde_id = request.GET.get('sonde_id')
    if not sonde_id:
        return HttpResponse('sonde_id required', status=400)
    
    try:
        sonde = Sonde.objects.get(sonde_id=sonde_id)
    except Sonde.DoesNotExist:
        return HttpResponse('sonde not found', status=404)

    telemetry = (
        Telemetry.objects
        .filter(sonde=sonde)
        .filter(temp__isnull=False, humidity__isnull=False)
        .order_by('alt')
        .values('alt', 'temp', 'humidity')
    )

    if not telemetry:
        return HttpResponse('no data', status=404)

    pressures, temps, dewpoints = [], [], []

    for t in telemetry:
        p = estimate_pressure(t['alt'], t['temp'], t['humidity'])
        dp = dewpoint(t['temp'], t['humidity'])
        pressures.append(p)
        temps.append(t['temp'])
        dewpoints.append(dp)

    pressures = np.array(pressures)
    temps = np.array(temps)
    dewpoints = np.array(dewpoints)

    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    # log pressure y axis
    ax.set_yscale('log')
    ax.set_ylim(1050, 100)
    ax.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax.set_yticks([1000, 850, 700, 500, 300, 200, 100])

    # skew angle
    SKEW = 45
    def skew_temp(T, P):
        return T + SKEW * np.log10(1013.25 / P)

    skewed_temps = skew_temp(temps, pressures)
    skewed_dews = skew_temp(dewpoints, pressures)

    for T0 in range(-40, 100, 10):
        T_line = T0 + 273.15
        P_line = np.linspace(1050, 100, 100)
        T_dry = (T_line * (P_line / 1013.25) ** 0.286) - 273.15
        ax.plot(skew_temp(T_dry, P_line), P_line, color='#2d6a4f', linewidth=0.5, alpha=0.5)

    # isotherms
    for T in range(-80, 50, 10):
        P_line = np.linspace(1050, 100, 100)
        ax.plot(skew_temp(np.full_like(P_line, T), P_line), P_line,
                color='#444', linewidth=0.5, alpha=0.6)
        ax.text(skew_temp(T, 1013), 1020, f'{T}°', fontsize=7,
                color='#888', ha='center')
        
    # temp line
    ax.plot(skewed_temps, pressures, color='#e63946', linewidth=2, label='Temperature')

    # dewpoint line
    ax.plot(skewed_dews, pressures, color='#457b9d', linewidth=2, label='Dewpoint')

    # style
    ax.set_xlabel('Temperature (°C)', color='white')
    ax.set_ylabel('Pressure (hPa)', color='white')
    ax.set_title(f'Skew-T  |  {sonde_id}', color='white', fontsize=13)
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(-40, 60)
    ax.grid(True, color='#333', linewidth=0.5)
    ax.legend(facecolor='#2a2a3e', labelcolor='white', fontsize=9)

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)

    return HttpResponse(buf, content_type='image/png')


def hodograph(request):
    if request.method != 'GET':
        return HttpResponse('GET only')

    sonde_id = request.GET.get('sonde_id')
    if not sonde_id:
        return HttpResponse('sonde_id required', status=400)

    try:
        sonde = Sonde.objects.get(sonde_id=sonde_id)
    except Sonde.DoesNotExist:
        return HttpResponse('sonde not found', status=404)

    telemetry = (
        Telemetry.objects
        .filter(sonde=sonde)
        .filter(vel_h__isnull=False, heading__isnull=False)
        .order_by('alt')
        .values('alt', 'vel_h', 'heading')
    )

    if not telemetry.exists():
        return HttpResponse('no data', status=404)

    u_vals = []
    v_vals = []
    alts = []

    for t in telemetry:
        speed = t['vel_h']
        heading = t['heading']

        theta = math.radians(heading)

        # meteorological convention
        u = -speed * math.sin(theta)
        v = -speed * math.cos(theta)

        u_vals.append(u)
        v_vals.append(v)
        alts.append(t['alt'])

    u_vals = np.array(u_vals)
    v_vals = np.array(v_vals)
    alts = np.array(alts)

    fig, ax = plt.subplots(figsize=(8, 8))

    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    # hodograph line
    ax.plot(
        u_vals,
        v_vals,
        color='#00d4ff',
        linewidth=2
    )

    # scatter points
    ax.scatter(
        u_vals,
        v_vals,
        c=alts,
        cmap='plasma',
        s=18,
        zorder=3
    )

    # altitude labels every N points
    step = max(1, len(alts) // 15)

    for i in range(0, len(alts), step):
        txt = ax.text(
            u_vals[i],
            v_vals[i],
            f'{int(alts[i]/1000)}km',
            fontsize=8,
            color='white'
        )

        txt.set_path_effects([
            pe.withStroke(linewidth=2, foreground='black')
        ])

    # axes lines
    ax.axhline(0, color='#666', linewidth=0.8)
    ax.axvline(0, color='#666', linewidth=0.8)

    # circles for wind speed
    max_r = int(np.ceil(max(np.sqrt(u_vals**2 + v_vals**2)) / 10.0) * 10)

    for r in range(10, max_r + 10, 10):
        circle = plt.Circle(
            (0, 0),
            r,
            color='#444',
            fill=False,
            linestyle='dashed',
            linewidth=0.6,
            alpha=0.5
        )
        ax.add_artist(circle)

        ax.text(
            r,
            0,
            f'{r}',
            color='#777',
            fontsize=7
        )

    # labels
    ax.set_xlabel('U Component', color='white')
    ax.set_ylabel('V Component', color='white')

    ax.set_title(
        f'Hodograph  |  {sonde_id}',
        color='white',
        fontsize=13
    )

    # equal aspect
    ax.set_aspect('equal', adjustable='box')

    # grid
    ax.grid(True, color='#333', linewidth=0.5)

    # ticks
    ax.tick_params(colors='white')

    # spines
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # limits
    lim = max_r + 10
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)

    buf = BytesIO()

    plt.tight_layout()

    plt.savefig(
        buf,
        format='png',
        dpi=120,
        facecolor=fig.get_facecolor()
    )

    plt.close()

    buf.seek(0)

    return HttpResponse(buf, content_type='image/png')



def check_key(request):
    key = request.headers.get("X-API-KEY")

    if not key:
        return None

    try:
        return APIKey.objects.select_related("user").get(key=key)
    except APIKey.DoesNotExist:
        return None


def sondes_by_date(request):
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)

    api_obj = check_key(request)
    if not api_obj:
        return JsonResponse({"error": "unauthorized"}, status=403)

    date_str = request.GET.get('date')
    if not date_str:
        return JsonResponse({'error': 'date is required'}, status=400)

    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return JsonResponse({'error': 'invalid date format YYYY-MM-DD'}, status=400)

    sonde_qs = Sonde.objects.filter(date__date=date_obj)

    data = list(sonde_qs.values("id", "sonde_id", "type", "subtype","date"))

    return JsonResponse({'data': data})

def sonde_data(request):
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)

    api_obj = check_key(request)
    if not api_obj:
        return JsonResponse({"error": "unauthorized"}, status=403)

    sonde_id = request.GET.get('sonde_id')
    if not sonde_id:
        return JsonResponse({'error': 'no sonde id'}, status=400)

    try:
        valid_sonde = Sonde.objects.get(sonde_id=sonde_id)
    except Sonde.DoesNotExist:
        return JsonResponse({'error': 'sonde id didnt match'}, status=404)

    sonde_data_qs = Telemetry.objects.filter(
        sonde=valid_sonde
    ).order_by('-frame').values(
        'frame', 'datetime',
        'lat', 'lon', 'alt',
        'vel_h', 'vel_v', 'heading',
        'temp', 'humidity', 'pressure',
        'battery', 'f_centre', 'snr'
    )

    return JsonResponse({
        "sonde_id": sonde_id,
        "data": list(sonde_data_qs)
    })

    

def sonde_KML(request):
    if request.method != 'GET':
        return JsonResponse({"error": "GET only"}, status=405)

    api_obj = check_key(request)
    if not api_obj:
        return JsonResponse({"error": "unauthorized"}, status=403)

    sonde_id = request.GET.get('sonde_id')
    if not sonde_id:
        return JsonResponse({'error': 'no sonde id'}, status=400)

    try:
        valid_sonde = Sonde.objects.get(sonde_id=sonde_id)
    except Sonde.DoesNotExist:
        return JsonResponse({'error': 'sonde id didnt match'}, status=404)

    data = Telemetry.objects.filter(
        sonde=valid_sonde
    ).order_by('frame').values('lat', 'lon', 'alt')

    coords = []
    for p in data:
        if p['lat'] is None or p['lon'] is None or p['alt'] is None:
            continue
        coords.append(f"{p['lon']},{p['lat']},{p['alt']}")

    coords_str = "\n".join(coords)


    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <kml xmlns="http://www.opengis.net/kml/2.2">
        <Document>

        <name>{sonde_id} Flight Path</name>

        <Placemark>
        <name>Sonde Path</name>

        <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>
        {coords_str}
        </coordinates>
        </LineString>

        </Placemark>

        </Document>
        </kml>
        """

    response = HttpResponse(
        kml.strip(),
        content_type="application/vnd.google-earth.kml+xml"
    )

    response["Content-Disposition"] = f'attachment; filename="{sonde_id}.kml"'

    return response
