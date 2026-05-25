from django.urls import path
from .views import chase_page

urlpatterns = [
    path('', chase_page, name='chase'),
]
