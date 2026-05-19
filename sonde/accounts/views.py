from django.shortcuts import render,redirect
from django.contrib.auth.decorators import login_required
from .models import Profile, APIKey

from .models import Profile, APIKey, ContributorInfo

@login_required
def dashboard(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    api_key = APIKey.objects.filter(user=request.user).first()

    contributor_info = None
    if profile.is_contributor:
        contributor_info, _ = ContributorInfo.objects.get_or_create(user=request.user)

    return render(request, "dashboard.html", {
        "user": request.user,
        "profile": profile,
        "api_key": api_key,
        "contributor_info": contributor_info
    })

@login_required
def update_role(request):
    if request.method == 'POST':
        profile, _ = Profile.objects.get_or_create(user=request.user)

        profile.is_api_user = 'is_api_user' in request.POST
        profile.is_contributor = 'is_contributor' in request.POST
        profile.save()

        if profile.is_contributor:
            info, _ = ContributorInfo.objects.get_or_create(user=request.user)

            info.lat = request.POST.get("lat") or None
            info.lon = request.POST.get("lon") or None
            info.alt = request.POST.get("alt") or None

            info.save()
        else:
            ContributorInfo.objects.filter(user=request.user).delete()

    return redirect('/accounts/dash/')