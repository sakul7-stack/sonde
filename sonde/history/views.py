from django.shortcuts import render
from tracker.models import Sonde,Telemetry,Prediction
from django.http import HttpResponse,JsonResponse


def history_data(request, n=5):

    if request.method != 'GET':
        return JsonResponse({'error': 'only get'})

    sondes = Sonde.objects.order_by('-date')[:n]

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

        result.append({
            'sonde_id': sonde.sonde_id,
            'type': sonde.type,
            'subtype': sonde.subtype,
            'frequency': sonde.frequency,
            'date': sonde.date,
            'data': list(telemetry)
        })

    return JsonResponse({'data': result})

def history(request):
    return render(request,'history.html')
