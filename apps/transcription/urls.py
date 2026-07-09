from django.urls import path
from . import views

urlpatterns = [
    path('segment/<uuid:session_id>/<int:segment_idx>/', views.edit_transcript_segment, name='edit-transcript-segment'),
]
