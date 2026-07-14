

from django.contrib import admin
from django.urls import path,include
from . import views


urlpatterns = [
 path('',views.history),
    path('data/',views.history_data),
    path('stats/',views.history_stats),
]