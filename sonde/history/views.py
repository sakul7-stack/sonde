from django.shortcuts import render
from tracker.models import Sonde, Telemetry
from django.http import JsonResponse
from django.db.models import Count, Max, Min, Avg
import json


def history_data(request):
    if request.method != 'GET':
        return JsonResponse({'error': 'only get'})

    sonde_id = request.GET.get('sonde_id', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    limit = int(request.GET.get('limit', 5))

    sondes = Sonde.objects.all()

    if sonde_id:
        sondes = sondes.filter(sonde_id__icontains=sonde_id)

    if date_from:
        sondes = sondes.filter(date__date__gte=date_from)

    if date_to:
        sondes = sondes.filter(date__date__lte=date_to)

    sondes = sondes.order_by('-date')[:limit]

    result = []

    for sonde in sondes:
        telemetry = Telemetry.objects.filter(
            sonde=sonde
        ).values(
            'frame',
            'datetime',
            'lat',
            'lon',
            'alt',
            'vel_h',
            'vel_v',
            'heading',
            'temp',
            'humidity',
            'pressure',
            'battery',
            'f_centre',
            'snr',
        ).order_by('datetime')

        telemetry_list = list(telemetry)

        max_alt = max((t['alt'] for t in telemetry_list), default=0)
        start_time = telemetry_list[0]['datetime'].isoformat() if telemetry_list else None
        end_time = telemetry_list[-1]['datetime'].isoformat() if telemetry_list else None

        result.append({
            'sonde_id': sonde.sonde_id,
            'type': sonde.type,
            'subtype': sonde.subtype,
            'frequency': sonde.frequency,
            'date': sonde.date.isoformat() if sonde.date else None,
            'data': telemetry_list,
            'stats': {
                'frames': len(telemetry_list),
                'max_alt': max_alt,
                'start_time': start_time,
                'end_time': end_time,
            }
        })

    return JsonResponse({'data': result})


def history_stats(request):
    total_flights = Sonde.objects.count()
    total_frames = Telemetry.objects.count()

    agg = Telemetry.objects.aggregate(
        max_alt=Max('alt'),
        avg_alt=Avg('alt'),
        min_temp=Min('temp'),
    )

    unique_types = Sonde.objects.exclude(type__isnull=True).exclude(type='').values_list('type', flat=True).distinct()

    date_range = Sonde.objects.aggregate(
        first_date=Min('date'),
        last_date=Max('date'),
    )

    return JsonResponse({
        'total_flights': total_flights,
        'total_frames': total_frames,
        'max_alt': agg['max_alt'],
        'avg_alt': round(agg['avg_alt'], 1) if agg['avg_alt'] else None,
        'min_temp': agg['min_temp'],
        'types': list(unique_types),
        'first_date': date_range['first_date'].isoformat() if date_range['first_date'] else None,
        'last_date': date_range['last_date'].isoformat() if date_range['last_date'] else None,
    })


def history(request):
    return render(request, 'history.html')
