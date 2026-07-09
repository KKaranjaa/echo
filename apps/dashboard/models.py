from django.db import models
from django.conf import settings
import uuid

class Tab(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='tabs')
    name = models.CharField(max_length=64)
    order = models.IntegerField(default=0)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']
        unique_together = [['user', 'name']]

    def __str__(self):
        return f"{self.name} ({self.user.email})"
