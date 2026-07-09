from django.urls import path
from . import views
from apps.summarisation import views as summary_views

urlpatterns = [
    path('', views.home, name='home'),
    path('upload/', views.upload_file, name='upload-file'),
    path('results/<uuid:session_id>/', summary_views.session_result, name='session-result'),
    # New: external URL ingestion
    path('sessions/from-url/', views.submit_url, name='submit-url'),
    path('sessions/<uuid:session_id>/status/', views.session_status, name='session-status'),
]
