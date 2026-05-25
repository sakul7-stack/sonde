from django.shortcuts import render
from tracker.models import Sonde, Telemetry
from accounts.models import Profile, APIKey, ContributorInfo
from django.http import JsonResponse, HttpResponse
from datetime import datetime
import math
from io import BytesIO

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np


def estimate_pressure(alt_m, temp_c, humidity_pct):
    """Virtual-temperature corrected barometric formula."""
    if humidity_pct <= 0:
        humidity_pct = 1
    T  = temp_c + 273.15
    es = 6.112 * math.exp((17.67 * temp_c) / (temp_c + 243.5))
    e  = (humidity_pct / 100.0) * es
    Tv = T / (1 - (e / 1013.25) * (1 - 0.622))
    H  = (287.05 * Tv) / 9.80665
    return 1013.25 * math.exp(-alt_m / H)


def dewpoint(temp_c, humidity_pct):
    """Magnus-formula dewpoint (°C)."""
    if humidity_pct <= 0:
        return temp_c - 30
    a, b  = 17.67, 243.5
    gamma = math.log(humidity_pct / 100.0) + (a * temp_c) / (b + temp_c)
    return (b * gamma) / (a - gamma)


def potential_temperature(temp_c, pressure_hpa):
    """Dry potential temperature θ (°C)."""
    return (temp_c + 273.15) * math.pow(1013.25 / pressure_hpa, 0.286) - 273.15


def equiv_potential_temperature(temp_c, dewpoint_c, pressure_hpa):
    """Equivalent potential temperature θe (°C) — Bolton 1980."""
    Tk = temp_c + 273.15
    # clamp dewpoint to avoid exp overflow
    dc = max(-80.0, min(60.0, dewpoint_c))
    es = 6.112 * math.exp(17.67 * dc / (dc + 243.5))
    denom = pressure_hpa - es
    if denom <= 0:
        return temp_c  # fallback
    ws = 0.622 * es / denom
    try:
        return Tk * math.pow(1013.25 / pressure_hpa, 0.286) * math.exp(2.5e6 * ws / (1004.0 * Tk)) - 273.15
    except (OverflowError, ValueError):
        return temp_c


def lcl_pressure(temp_c, dewpoint_c, pressure_hpa):
    """Lifting Condensation Level pressure (hPa) — Bolton 1980."""
    Tk = temp_c + 273.15
    Td = dewpoint_c + 273.15
    if Td <= 56 or Tk <= 0:
        return pressure_hpa * 0.9  # rough fallback
    T_lcl = 1.0 / (1.0 / (Td - 56) + math.log(Tk / Td) / 800.0) + 56
    return pressure_hpa * math.pow(T_lcl / Tk, 3.4965)



def compute_cape_cin(levels):
    """
    Parcel-theory CAPE & CIN with overflow/bad-data guards.
    levels: list of dicts sorted surface→top,
            keys: pressure, temp, dewpoint, alt
    Returns (CAPE, CIN) in J/kg.
    """
    if not levels:
        return 0.0, 0.0

    sfc   = levels[0]
    p_sfc = sfc['pressure']
    T_sfc = sfc['temp'] + 273.15
    Td_sfc = sfc['dewpoint'] + 273.15

    if T_sfc <= 0 or Td_sfc <= 0 or p_sfc <= 0:
        return 0.0, 0.0

    Lv = 2.5e6
    Rd = 287.05
    cp = 1004.0

    # LCL
    try:
        T_lcl = 1.0 / (1.0 / (Td_sfc - 56) + math.log(T_sfc / Td_sfc) / 800.0) + 56
        p_lcl = p_sfc * math.pow(T_lcl / T_sfc, 3.4965)
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0, 0.0

    cape     = 0.0
    cin      = 0.0
    T_parcel = T_sfc

    for i in range(1, len(levels)):
        prev  = levels[i - 1]
        curr  = levels[i]
        p1    = prev['pressure']
        p2    = curr['pressure']

        if p1 <= 0 or p2 <= 0 or p1 <= p2:
            continue

        dp    = p1 - p2
        p_mid = (p1 + p2) / 2.0

        try:
            if p_mid > p_lcl:
                # dry adiabatic
                T_parcel *= math.pow(p2 / p1, Rd / cp)
            else:
                # moist adiabatic — 3-step iteration
                for _ in range(3):
                    Tp = T_parcel
                    Tc = max(-80.0, min(60.0, Tp - 273.15))
                    es_p = 6.112 * math.exp(17.67 * Tc / (Tc + 243.5))
                    denom_ws = p_mid - es_p
                    if denom_ws <= 0:
                        break
                    ws_p = 0.622 * es_p / denom_ws
                    num  = Rd * Tp + Lv * ws_p
                    den  = cp + (Lv * Lv * ws_p * 0.622) / (Rd * Tp * Tp)
                    if den == 0:
                        break
                    T_parcel -= (Rd * Tp / p1) * (num / den) / cp * dp

            if not math.isfinite(T_parcel) or T_parcel <= 0 or T_parcel > 400:
                break

        except (OverflowError, ValueError, ZeroDivisionError):
            break

        T_env = curr['temp'] + 273.15
        if T_env <= 0:
            continue

        dz = (Rd * T_env / (9.80665 * p_mid)) * dp * 100.0
        dT = T_parcel - T_env

        if dT >= 0:
            cape += 9.80665 * (dT / T_env) * dz
        else:
            if cape == 0.0:
                cin += 9.80665 * (dT / T_env) * dz

    return round(max(cape, 0.0), 1), round(min(cin, 0.0), 1)


def compute_indices(levels):
    """
    Common sounding indices with per-index error guards.
    levels: list sorted surface→top (highest pressure first).
    """
    if not levels:
        return {}

    sfc = levels[0]

    def find_level(target_p, tol=25):
        return next((l for l in levels if abs(l['pressure'] - target_p) < tol), None)

    T850 = find_level(850)
    T700 = find_level(700)
    T500 = find_level(500)

    # CAPE / CIN
    try:
        cape, cin = compute_cape_cin(levels)
    except Exception:
        cape, cin = 0.0, 0.0

    # Lifted index
    li = None
    try:
        if T500:
            parcel_500 = sfc['temp'] - 6.5 * (T500['alt'] - sfc['alt']) / 1000.0
            li = round(T500['temp'] - parcel_500, 1)
    except Exception:
        pass

    # K-index
    ki = None
    try:
        if T850 and T700 and T500:
            ki = round(
                (T850['temp'] - T500['temp'])
                + T850['dewpoint']
                - (T700['temp'] - T700['dewpoint']),
                1
            )
    except Exception:
        pass

    # Showalter index
    si = None
    try:
        if T500 and T850:
            parcel_850 = sfc['temp'] - 6.5 * (T850['alt'] - sfc['alt']) / 1000.0
            si = round(T500['temp'] - parcel_850, 1)
    except Exception:
        pass

    # Total-Totals
    tt = None
    try:
        if T850 and T500:
            tt = round(T850['temp'] + T850['dewpoint'] - 2 * T500['temp'], 1)
    except Exception:
        pass

    # Precipitable water (mm)
    pw = 0.0
    try:
        for i in range(1, len(levels)):
            dp = levels[i - 1]['pressure'] - levels[i]['pressure']
            if dp <= 0:
                continue
            rh   = (levels[i - 1]['humidity'] + levels[i]['humidity']) / 2.0
            T_av = (levels[i - 1]['temp'] + levels[i]['temp']) / 2.0
            Tc   = max(-80.0, min(60.0, T_av))
            es   = 6.112 * math.exp(17.67 * Tc / (Tc + 243.5))
            e    = (rh / 100.0) * es
            denom = levels[i]['pressure'] - e
            if denom <= 0:
                continue
            w  = 0.622 * e / denom
            pw += w * dp * 100.0 / 9.80665
    except Exception:
        pw = 0.0
    pw = round(pw, 1)

    # LCL
    lcl_p = None
    try:
        lcl_p = round(lcl_pressure(sfc['temp'], sfc['dewpoint'], sfc['pressure']), 1)
    except Exception:
        pass

    # Tropopause — first inversion below 300 hPa
    trop_p = trop_alt = None
    try:
        for i in range(2, len(levels)):
            if levels[i]['pressure'] < 300 and levels[i]['temp'] > levels[i - 1]['temp']:
                trop_p   = round(levels[i]['pressure'], 1)
                trop_alt = round(levels[i]['alt'] / 1000.0, 2)
                break
    except Exception:
        pass

    # Wind shear helpers
    def uv(d):
        try:
            if d.get('vel_h') is None or d.get('heading') is None:
                return None, None
            th = math.radians(d['heading'])
            return -d['vel_h'] * math.sin(th), -d['vel_h'] * math.cos(th)
        except Exception:
            return None, None

    shear_01 = shear_06 = None
    try:
        sfc_u, sfc_v = uv(sfc)
        if sfc_u is not None:
            km1 = min(levels, key=lambda l: abs(l['alt'] - 1000))
            km6 = min(levels, key=lambda l: abs(l['alt'] - 6000))
            u1, v1 = uv(km1)
            if u1 is not None:
                shear_01 = round(math.sqrt((u1 - sfc_u)**2 + (v1 - sfc_v)**2), 1)
            u6, v6 = uv(km6)
            if u6 is not None:
                shear_06 = round(math.sqrt((u6 - sfc_u)**2 + (v6 - sfc_v)**2), 1)
    except Exception:
        pass

    # Max wind
    max_wind = None
    try:
        wind_levels = [l for l in levels if l.get('vel_h') is not None]
        if wind_levels:
            max_wind = max(wind_levels, key=lambda l: l['vel_h'])
    except Exception:
        pass

    return {
        'cape':           cape,
        'cin':            cin,
        'li':             li,
        'k_index':        ki,
        'showalter':      si,
        'total_totals':   tt,
        'pw_mm':          pw,
        'lcl_hpa':        lcl_p,
        'tropopause_hpa': trop_p,
        'tropopause_km':  trop_alt,
        'shear_01_ms':    shear_01,
        'shear_06_ms':    shear_06,
        'max_wind_ms':    round(max_wind['vel_h'], 1) if max_wind else None,
        'max_wind_hpa':   round(max_wind['pressure'], 1) if max_wind else None,
        'max_wind_dir':   max_wind['heading'] if max_wind else None,
    }


def check_key(request):
    key = request.headers.get("X-API-KEY")
    if not key:
        return None
    try:
        return APIKey.objects.select_related("user").get(key=key)
    except APIKey.DoesNotExist:
        return None



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
        .values('alt', 'temp', 'humidity', 'vel_h', 'heading')
    )

    if not telemetry:
        return HttpResponse('no data', status=404)

    pressures, temps, dewpoints_list = [], [], []
    wind_pressures, wind_u, wind_v   = [], [], []

    for t in telemetry:
        p  = estimate_pressure(t['alt'], t['temp'], t['humidity'])
        dp = dewpoint(t['temp'], t['humidity'])
        pressures.append(p)
        temps.append(t['temp'])
        dewpoints_list.append(dp)

        if t['vel_h'] is not None and t['heading'] is not None:
            theta = math.radians(t['heading'])
            wind_pressures.append(p)
            wind_u.append(-t['vel_h'] * math.sin(theta))
            wind_v.append(-t['vel_h'] * math.cos(theta))

    pressures      = np.array(pressures)
    temps          = np.array(temps)
    dewpoints_arr  = np.array(dewpoints_list)

    fig, (ax, ax_wind) = plt.subplots(
        1, 2, figsize=(10, 10),
        gridspec_kw={'width_ratios': [5, 1]}
    )
    fig.patch.set_facecolor('#1a1a2e')

    ax.set_facecolor('#1a1a2e')
    ax.set_yscale('log')
    ax.set_ylim(1050, 100)
    ax.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax.set_yticks([1000, 850, 700, 500, 300, 200, 100])

    SKEW = 45
    def skew_temp(T, P):
        return T + SKEW * np.log10(1013.25 / P)

    skewed_temps = skew_temp(temps, pressures)
    skewed_dews  = skew_temp(dewpoints_arr, pressures)

    for T0 in range(-40, 100, 10):
        P_line = np.linspace(1050, 100, 100)
        T_dry  = ((T0 + 273.15) * (P_line / 1013.25) ** 0.286) - 273.15
        ax.plot(skew_temp(T_dry, P_line), P_line, color='#2d6a4f', linewidth=0.5, alpha=0.5)

    for T in range(-80, 50, 10):
        P_line = np.linspace(1050, 100, 100)
        ax.plot(skew_temp(np.full_like(P_line, T), P_line), P_line,
                color='#444', linewidth=0.5, alpha=0.6)
        ax.text(skew_temp(T, 1013), 1020, f'{T}°', fontsize=7, color='#888', ha='center')

    ax.plot(skewed_temps, pressures, color='#e63946', linewidth=2, label='Temperature')
    ax.plot(skewed_dews,  pressures, color='#457b9d', linewidth=2, label='Dewpoint')

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

    ax_wind.set_facecolor('#1a1a2e')
    ax_wind.set_yscale('log')
    ax_wind.set_ylim(1050, 100)
    ax_wind.set_yticks([1000, 850, 700, 500, 300, 200, 100])
    ax_wind.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax_wind.set_xlim(-0.5, 0.5)
    ax_wind.set_xticks([])
    ax_wind.tick_params(colors='white', left=False, labelleft=False)
    ax_wind.set_title('Wind', color='white', fontsize=10)
    ax_wind.spines['bottom'].set_color('#555')
    ax_wind.spines['left'].set_color('#555')
    ax_wind.spines['top'].set_visible(False)
    ax_wind.spines['right'].set_visible(False)
    ax_wind.grid(True, color='#333', linewidth=0.5)

    if wind_pressures:
        wp = np.array(wind_pressures)
        wu = np.array(wind_u)
        wv = np.array(wind_v)
        indices = np.unique(
            np.round(np.linspace(0, len(wp) - 1, min(20, len(wp)))).astype(int)
        )
        ax_wind.barbs(
            np.zeros_like(wp[indices]), wp[indices],
            wu[indices], wv[indices],
            length=6, linewidth=0.8, color='#f4d35e', zorder=3
        )

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

    u_vals, v_vals, alts = [], [], []
    for t in telemetry:
        theta = math.radians(t['heading'])
        u_vals.append(-t['vel_h'] * math.sin(theta))
        v_vals.append(-t['vel_h'] * math.cos(theta))
        alts.append(t['alt'])

    u_vals = np.array(u_vals)
    v_vals = np.array(v_vals)
    alts   = np.array(alts)

    fig, ax = plt.subplots(figsize=(8, 8))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')

    ax.plot(u_vals, v_vals, color='#00d4ff', linewidth=2)
    ax.scatter(u_vals, v_vals, c=alts, cmap='plasma', s=18, zorder=3)

    step = max(1, len(alts) // 15)
    for i in range(0, len(alts), step):
        txt = ax.text(u_vals[i], v_vals[i], f'{int(alts[i]/1000)}km',
                      fontsize=8, color='white')
        txt.set_path_effects([pe.withStroke(linewidth=2, foreground='black')])

    ax.axhline(0, color='#666', linewidth=0.8)
    ax.axvline(0, color='#666', linewidth=0.8)

    max_r = int(np.ceil(max(np.sqrt(u_vals**2 + v_vals**2)) / 10.0) * 10)
    for r in range(10, max_r + 10, 10):
        ax.add_artist(plt.Circle((0, 0), r, color='#444', fill=False,
                                  linestyle='dashed', linewidth=0.6, alpha=0.5))
        ax.text(r, 0, f'{r}', color='#777', fontsize=7)

    ax.set_xlabel('U Component', color='white')
    ax.set_ylabel('V Component', color='white')
    ax.set_title(f'Hodograph  |  {sonde_id}', color='white', fontsize=13)
    ax.set_aspect('equal', adjustable='box')
    ax.grid(True, color='#333', linewidth=0.5)
    ax.tick_params(colors='white')
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    lim = max_r + 10
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


def emagram(request):
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
        .filter(temp__isnull=False, humidity__isnull=False, alt__isnull=False)
        .order_by('alt')
        .values('alt', 'temp', 'humidity')
    )

    if not telemetry.exists():
        return HttpResponse('no data', status=404)

    pressures, temps, dewpoints_list = [], [], []
    for t in telemetry:
        pressures.append(estimate_pressure(t['alt'], t['temp'], t['humidity']))
        temps.append(t['temp'])
        dewpoints_list.append(dewpoint(t['temp'], t['humidity']))

    pressures = np.array(pressures)
    temps     = np.array(temps)
    dews      = np.array(dewpoints_list)

    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    ax.set_yscale('log')
    ax.set_ylim(1050, 100)
    ax.set_yticks([1000, 850, 700, 500, 300, 200, 100])
    ax.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax.set_xlim(-40, 60)

    P_line = np.linspace(1050, 100, 100)
    for T in range(-80, 50, 10):
        ax.plot(np.full_like(P_line, T), P_line, color='#444', linewidth=0.6, alpha=0.5)
        ax.text(T, 1020, f'{T}°', color='#888', fontsize=7, ha='center')

    for theta in range(220, 380, 10):
        P = np.linspace(1050, 100, 120)
        ax.plot(theta * (P / 1013.25) ** 0.286 - 273.15, P,
                color='#2d6a4f', linewidth=0.5, alpha=0.4)

    ax.plot(temps, pressures, color='#e63946', linewidth=2, label='Temperature')
    ax.plot(dews,  pressures, color='#457b9d', linewidth=2, label='Dewpoint')
    ax.set_xlabel('Temperature (°C)', color='white')
    ax.set_ylabel('Pressure (hPa)', color='white')
    ax.set_title(f'Emagram | {sonde_id}', color='white')
    ax.tick_params(colors='white')
    ax.grid(True, color='#333', linewidth=0.5)
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#2a2a3e', labelcolor='white')

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


def tephigram(request):
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
        .filter(temp__isnull=False, humidity__isnull=False, alt__isnull=False)
        .order_by('alt')
        .values('alt', 'temp', 'humidity')
    )

    if not telemetry.exists():
        return HttpResponse('no data', status=404)

    pressures, temps, dewpoints_list = [], [], []
    for t in telemetry:
        pressures.append(estimate_pressure(t['alt'], t['temp'], t['humidity']))
        temps.append(t['temp'])
        dewpoints_list.append(dewpoint(t['temp'], t['humidity']))

    pressures = np.array(pressures)
    temps     = np.array(temps)
    dews      = np.array(dewpoints_list)

    fig, ax = plt.subplots(figsize=(9, 11))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    ax.set_yscale('log')
    ax.set_ylim(1050, 100)
    ax.set_yticks([1000, 850, 700, 500, 300, 200, 100])
    ax.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax.set_xlim(-80, 40)

    P_line = np.linspace(1050, 100, 200)
    for T in range(-80, 45, 10):
        ax.plot(np.full_like(P_line, T), P_line, color='#444', linewidth=0.6, alpha=0.6)
        ax.text(T, 1020, f'{T}°', color='#888', fontsize=8, ha='center')

    for theta_k in range(230, 400, 10):
        P = np.linspace(1050, 100, 150)
        ax.plot(theta_k * (P / 1013.25) ** 0.2854 - 273.15, P,
                color='#2d6a4f', linewidth=0.7, alpha=0.5)

    ax.plot(temps, pressures, color='#e63946', linewidth=2.5, label='Temperature')
    ax.plot(dews,  pressures, color='#457b9d', linewidth=2.5, label='Dewpoint')
    ax.set_xlabel('Temperature (°C)', color='white', fontsize=11)
    ax.set_ylabel('Pressure (hPa)', color='white', fontsize=11)
    ax.set_title(f'Tephigram | {sonde_id}', color='white', fontsize=14)
    ax.tick_params(colors='white')
    ax.grid(True, color='#333', linewidth=0.5)
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#2a2a3e', labelcolor='white')

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=130, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


def stuve(request):
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
        .filter(temp__isnull=False, humidity__isnull=False, alt__isnull=False)
        .order_by('alt')
        .values('alt', 'temp', 'humidity')
    )

    if not telemetry.exists():
        return HttpResponse('no data', status=404)

    pressures, temps, dewpoints_list = [], [], []
    for t in telemetry:
        pressures.append(estimate_pressure(t['alt'], t['temp'], t['humidity']))
        temps.append(t['temp'])
        dewpoints_list.append(dewpoint(t['temp'], t['humidity']))

    pressures = np.array(pressures)
    temps     = np.array(temps)
    dews      = np.array(dewpoints_list)

    fig, ax = plt.subplots(figsize=(8, 10))
    fig.patch.set_facecolor('#1a1a2e')
    ax.set_facecolor('#1a1a2e')
    ax.set_yscale('log')
    ax.set_ylim(1050, 100)
    ax.set_yticks([1000, 850, 700, 500, 300, 200, 100])
    ax.yaxis.set_major_formatter(plt.ScalarFormatter())
    ax.set_xlim(-40, 60)

    P_line = np.linspace(1050, 100, 100)
    for T in range(-80, 50, 10):
        ax.plot(np.full_like(P_line, T), P_line, color='#444', linewidth=0.6, alpha=0.5)
        ax.text(T, 1020, f'{T}°', color='#888', fontsize=7, ha='center')

    for theta in range(220, 380, 10):
        P = np.linspace(1050, 100, 120)
        ax.plot(theta * (P / 1013.25) ** 0.286 - 273.15, P,
                color='#2d6a4f', alpha=0.4, linewidth=0.5)

    ax.plot(temps, pressures, color='#e63946', linewidth=2, label='Temperature')
    ax.plot(dews,  pressures, color='#457b9d', linewidth=2, label='Dewpoint')
    ax.set_xlabel('Temperature (°C)', color='white')
    ax.set_ylabel('Pressure (hPa)', color='white')
    ax.set_title(f'Stüve | {sonde_id}', color='white')
    ax.tick_params(colors='white')
    ax.grid(True, color='#333', linewidth=0.5)
    ax.spines['bottom'].set_color('#555')
    ax.spines['left'].set_color('#555')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(facecolor='#2a2a3e', labelcolor='white')

    buf = BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png', dpi=120, facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return HttpResponse(buf, content_type='image/png')


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
    data = list(sonde_qs.values("id", "sonde_id", "type", "subtype", "date"))
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

    qs = Telemetry.objects.filter(sonde=valid_sonde).order_by('-frame').values(
        'frame', 'datetime', 'lat', 'lon', 'alt',
        'vel_h', 'vel_v', 'heading',
        'temp', 'humidity', 'pressure',
        'battery', 'f_centre', 'snr'
    )
    return JsonResponse({"sonde_id": sonde_id, "data": list(qs)})


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

    data = Telemetry.objects.filter(sonde=valid_sonde).order_by('frame').values('lat', 'lon', 'alt')
    coords = [
        f"{p['lon']},{p['lat']},{p['alt']}"
        for p in data
        if p['lat'] is not None and p['lon'] is not None and p['alt'] is not None
    ]

    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
<Document>
<name>{sonde_id} Flight Path</name>
<Placemark>
    <name>Sonde Path</name>
    <LineString>
        <altitudeMode>absolute</altitudeMode>
        <coordinates>
{chr(10).join(coords)}
        </coordinates>
    </LineString>
</Placemark>
</Document>
</kml>"""

    response = HttpResponse(kml.strip(), content_type="application/vnd.google-earth.kml+xml")
    response["Content-Disposition"] = f'attachment; filename="{sonde_id}.kml"'
    return response


def sonde_atmosphere_json(request):
    """
    GET /data/atmosphere/?sonde_id=<id>
    Returns per-level telemetry with estimated pressure, dewpoint,
    wind components, potential temperatures, and instability indices.
    """
    if request.method != 'GET':
        return JsonResponse({'error': 'GET only'}, status=405)

    sonde_id = request.GET.get('sonde_id', '').strip()
    if not sonde_id:
        return JsonResponse({'error': 'sonde_id required'}, status=400)

    try:
        sonde = Sonde.objects.get(sonde_id=sonde_id)
    except Sonde.DoesNotExist:
        return JsonResponse({'error': 'sonde not found'}, status=404)

    qs = (
        Telemetry.objects
        .filter(sonde=sonde)
        .filter(temp__isnull=False, humidity__isnull=False, alt__isnull=False)
        .order_by('alt')
        .values('frame', 'datetime', 'alt', 'temp', 'humidity',
                'vel_h', 'heading', 'vel_v', 'pressure', 'snr')
    )

    if not qs:
        return JsonResponse({'error': 'no telemetry data'}, status=404)

    levels = []
    for t in qs:
        p_est = estimate_pressure(t['alt'], t['temp'], t['humidity'])
        dp    = dewpoint(t['temp'], t['humidity'])
        th    = potential_temperature(t['temp'], p_est)
        the   = equiv_potential_temperature(t['temp'], dp, p_est)

        u = v = None
        if t['vel_h'] is not None and t['heading'] is not None:
            rad = math.radians(t['heading'])
            u   = round(-t['vel_h'] * math.sin(rad), 3)
            v   = round(-t['vel_h'] * math.cos(rad), 3)

        levels.append({
            'frame':                t['frame'],
            'datetime':             t['datetime'],
            'alt':                  t['alt'],
            'pressure_estimated':   round(p_est, 2),
            'pressure_measured':    t['pressure'],
            'temp':                 t['temp'],
            'dewpoint':             round(dp, 2),
            'humidity':             t['humidity'],
            'potential_temp':       round(th, 2),
            'equiv_potential_temp': round(the, 2),
            'vel_h':                t['vel_h'],
            'vel_v':                t['vel_v'],
            'heading':              t['heading'],
            'wind_u':               u,
            'wind_v':               v,
            'snr':                  t['snr'],
        })

    # sort surface → top
    levels_sorted = sorted(levels, key=lambda l: -l['pressure_estimated'])

    idx_input = [{
        'pressure':  l['pressure_estimated'],
        'temp':      l['temp'],
        'dewpoint':  l['dewpoint'],
        'humidity':  l['humidity'],
        'alt':       l['alt'],
        'vel_h':     l['vel_h'],
        'heading':   l['heading'],
    } for l in levels_sorted]

    indices = compute_indices(idx_input)

    return JsonResponse({
        'sonde_id': sonde_id,
        'type':     sonde.type,
        'subtype':  sonde.subtype,
        'date':     str(sonde.date),
        'levels':   len(levels),
        'indices':  indices,
        'data':     levels_sorted,
    })



