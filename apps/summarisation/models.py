from django.db import models
from apps.uploads.models import Session

class Summary(models.Model):
    session = models.OneToOneField(Session, on_delete=models.CASCADE, related_name='summary')
    key_points = models.JSONField(default=list)
    exam_flags = models.JSONField(default=list)
    action_items = models.JSONField(default=list)
    flashcards = models.JSONField(default=list)
    summary_paragraph = models.TextField()
    prompt_version = models.CharField(max_length=20)
    starter_questions = models.JSONField(default=list)
    strict_exam_flags = models.JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f"Summary for Session {self.session_id}"
