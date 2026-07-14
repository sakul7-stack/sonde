from django.urls import path
from . import views

urlpatterns = [
    path('dash/', views.dashboard),
    path('update-role/', views.update_role),
]