from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index_Intime_Camera, name='index_Intime_Camera'),
    path('Intime_Camera/', views.index_Intime_Camera, name='index_Intime_Camera'),
    path('video/<str:camera_id>/', views.video_feed, name='video_feed'),
    path('get_camera_fps/', views.get_camera_fps, name='get_camera_fps'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
