from celery import shared_task
from django.utils import timezone
from django.conf import settings
from .models import Session
import os
import shutil
import logging

logger = logging.getLogger(__name__)

@shared_task
def cleanup_expired_sessions():
    expired = Session.objects.filter(expires_at__lt=timezone.now())
    count = 0
    freed_bytes = 0
    for session in expired:
        media_path = os.path.join(settings.MEDIA_ROOT, 'uploads', str(session.id))
        if os.path.exists(media_path):
            freed_bytes += sum(
                os.path.getsize(os.path.join(media_path, f))
                for f in os.listdir(media_path)
            )
            shutil.rmtree(media_path)
        count += 1
    expired.delete()
    logger.info(f'Cleaned {count} sessions, freed {freed_bytes // (1024*1024)} MB')
