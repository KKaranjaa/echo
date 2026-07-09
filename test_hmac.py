import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'echo.settings.development')
django.setup()

from allauth.account.models import EmailAddress, EmailConfirmationHMAC
from django.contrib.auth import get_user_model
from django.core import signing
from allauth.account import app_settings

User = get_user_model()
user = User.objects.first()
email_address = EmailAddress.objects.filter(user=user).first()
key = EmailConfirmationHMAC(email_address).key

def get_hmac_confirmation(key):
    try:
        max_age = 60 * 60 * 24 * app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
        pk = signing.loads(key, max_age=max_age, salt=app_settings.SALT)
        email_address = EmailAddress.objects.get(pk=pk)
        return EmailConfirmationHMAC(email_address)
    except Exception as e:
        print("Error:", e)
        return None

conf = get_hmac_confirmation(key)
print("Found confirmation:", conf)
