#camerain/urls.py

from django.urls import path,include

urlpatterns = [
    path('',include("camerain_app.urls")),
]
