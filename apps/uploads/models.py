import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone

def default_expires_at():
    return timezone.now() + timedelta(hours=24)

class Session(models.Model):
    STATUS_CHOICES = [
        ('initiated', 'Initiated'),
        ('fetching_metadata', 'Fetching Metadata'),
        ('downloading', 'Downloading'),
        ('uploading', 'Uploading'),
        ('transcribing', 'Transcribing'),
        ('summarising', 'Summarising'),
        ('complete', 'Complete'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=default_expires_at)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='uploading')
    detected_language = models.CharField(max_length=10, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    original_filename = models.CharField(max_length=255)
    error_detail = models.TextField(blank=True)
    # URL ingestion fields — null for direct uploads
    source_url = models.URLField(max_length=2048, null=True, blank=True)
    source_platform = models.CharField(max_length=64, null=True, blank=True)


    def __str__(self):
        return f"Session {self.id} ({self.status})"

    @property
    def audio_url(self):
        import os
        from django.conf import settings
        try:
            ext = os.path.splitext(self.original_filename)[1].lower()
            return f"{settings.MEDIA_URL}uploads/{self.id}/original_audio{ext}"
        except Exception:
            return ""
