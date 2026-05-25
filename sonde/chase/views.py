

# Create your views here.
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required
def chase_page(request):
    return render(request, 'chase/chase.html')
