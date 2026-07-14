from django.shortcuts import render, redirect
from .forms import UserSubmitForm

def submit_report(request):
    if request.method == "POST":
        form = UserSubmitForm(request.POST, request.FILES)
        
        if form.is_valid():
            form.save()
            return render(request, 'submit.html', {'success': True})

    else:
        form = UserSubmitForm()

    return render(request, 'submit.html', {'form': form})