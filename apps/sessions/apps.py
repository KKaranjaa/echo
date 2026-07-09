from django.apps import AppConfig


class EchoSessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sessions"
    label = "echo_sessions"  # avoid clash with django.contrib.sessions
