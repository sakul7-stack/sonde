from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from .models import Profile, APIKey, ContributorInfo
from tracker.models import Sonde, Telemetry


@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    api_key = APIKey.objects.filter(user=request.user).first()

    contributor_info = None
    if profile.is_contributor:
        contributor_info, _ = ContributorInfo.objects.get_or_create(user=request.user)

    sonde_count = Sonde.objects.count()
    latest_sonde = Sonde.objects.order_by('-date').first()

    return render(request, "dashboard.html", {
        "user": request.user,
        "profile": profile,
        "api_key": api_key,
        "contributor_info": contributor_info,
        "sonde_count": sonde_count,
        "latest_sonde": latest_sonde,
    })

@login_required
def update_role(request):
    if request.method == 'POST':
        profile, _ = Profile.objects.get_or_create(user=request.user)

        profile.is_api_user = 'is_api_user' in request.POST
        profile.is_contributor = 'is_contributor' in request.POST
        profile.save()

        # handle contributor info
        if profile.is_contributor:
            info, _ = ContributorInfo.objects.get_or_create(user=request.user)

            info.lat = request.POST.get("lat") or None
            info.lon = request.POST.get("lon") or None
            info.alt = request.POST.get("alt") or None

            info.save()
        else:
            # optional: remove data if unchecked
            ContributorInfo.objects.filter(user=request.user).delete()

    return redirect('/accounts/dash/')