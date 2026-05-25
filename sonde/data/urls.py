    
from django.urls import path
from . import views

urlpatterns = [
    path('data_by_date/', views.sondes_by_date),
    path('sonde_data/', views.sonde_data),
    path('sonde_KML/', views.sonde_KML),
    path('skewt/', views.skewt),
path('hodograph/', views.hodograph),
    path('atmosphere/', views.sonde_atmosphere_json),
]
    
