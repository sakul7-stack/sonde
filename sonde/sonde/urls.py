"""
URL configuration for sonde project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path,include
from tracker import views


urlpatterns = [
    path('secret-dashboard-92x/', admin.site.urls),
    path('api/ingest/', views.ingest),
    path('api/sondes/',views.sondes),
    path('api/pred/',views.predict_path),
    path('',views.home),
    path('3d/',views.view_3d),
    path('faq/',views.faq),
    path('api-doc/',views.api_doc),
    path('predict/',views.predict),
    path('predict_prox/',views.predict_prox),
    path('burst/',views.burst),
    path('skewt/', views.skewt_page),
    

    path('report/', include('reportsonde.urls')), 
    path('accounts/', include('accounts.urls')),
    path('accounts/', include('allauth.urls')),
    path('data/', include('data.urls')),
    path('history/',include('history.urls')),
    path('chase/', include('chase.urls')),
]
