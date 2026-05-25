
from django.conf import settings
from django.conf.urls.static import static

from django.contrib import admin
from django.urls import path,include
from tracker import views


urlpatterns = [
    path('portal-7721/', admin.site.urls),
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
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
