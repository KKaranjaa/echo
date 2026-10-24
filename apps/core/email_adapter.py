"""
Custom allauth AccountAdapter.

Wraps send_mail() so that any SMTP / network error is logged but never
propagates to the user — a failed verification email will not crash the
signup page or the resend flow, even on Render's free tier.
"""
import logging
from allauth.account.adapter import DefaultAccountAdapter

logger = logging.getLogger(__name__)


class SafeEmailAdapter(DefaultAccountAdapter):
    """
    Identical to DefaultAccountAdapter except send_mail() never raises.
    If the SMTP connection fails (e.g. missing credentials, timeout, port
    blocked) the error is logged as a WARNING and execution continues.
    """

    def send_mail(self, template_prefix, email, context):
        try:
            super().send_mail(template_prefix, email, context)
        except Exception as exc:
            logger.warning(
                "Failed to send email to %s (template: %s): %s. "
                "Check EMAIL_HOST_USER / EMAIL_HOST_PASSWORD env vars on Render.",
                email, template_prefix, exc,
            )
            if hasattr(self, "request") and self.request:
                from django.contrib import messages
                messages.warning(
                    self.request,
                    "Notice: Verification email could not be dispatched via SMTP. "
                    "If using Gmail, ensure an App Password is set in Render environment variables."
                )
