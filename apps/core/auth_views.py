"""
Custom auth views that extend allauth's built-in behaviour.
"""
from django.shortcuts import redirect
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress, EmailConfirmationHMAC, EmailConfirmation

User = get_user_model()

@require_POST
def request_magic_link(request):
    """
    Handles the "Send Magic Link" form submission.
    Creates a user if they don't exist, and sends an allauth email confirmation.
    """
    email = request.POST.get('login', '').strip().lower()
    if not email:
        messages.error(request, "Please provide a valid email address.")
        return redirect('account_login')

    # Get or create the user
    user, created = User.objects.get_or_create(email=email, defaults={'username': email})
    
    # Ensure allauth knows about this email
    email_address, _ = EmailAddress.objects.get_or_create(
        user=user, 
        email=email,
        defaults={'primary': True, 'verified': False}
    )

    # Send the allauth confirmation email (which acts as our magic link)
    email_address.send_confirmation(request, signup=created)

    messages.success(request, f"A magic link has been sent to {email}. Check your inbox!")
    return redirect('account_login')

from django.shortcuts import render
from django.contrib.auth import login
from django.core import signing
from allauth.account import app_settings

def get_hmac_confirmation(key):
    """
    Decodes the HMAC key bypassing allauth's `verified=False` check.
    This allows Magic Links to work for returning users who are already verified!
    """
    try:
        max_age = 60 * 60 * 24 * app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS
        pk = signing.loads(key, max_age=max_age, salt=app_settings.SALT)
        email_address = EmailAddress.objects.get(pk=pk)
        return EmailConfirmationHMAC(email_address)
    except Exception:
        return None

def custom_confirm_email(request, key):
    """
    Replaces allauth's ConfirmEmailView.
    Renders our styled template on GET.
    On POST, confirms the email and GUARANTEES the user is logged in (Magic Link behavior).
    """
    # Try our custom HMAC decode first (works for returning users)
    confirmation = get_hmac_confirmation(key)
    
    # Fallback to older DB-based keys
    if not confirmation:
        try:
            confirmation = EmailConfirmation.objects.get(key=key.lower())
        except EmailConfirmation.DoesNotExist:
            confirmation = None

    if request.method == "POST":
        if not confirmation:
            messages.error(request, "This magic link has expired or is invalid.")
            return redirect('account_login')
        
        # Confirm the email
        confirmation.confirm(request)
        
        # MAGIC LINK: Guarantee the user is logged in
        # specify the allauth backend to avoid multiple backends error
        login(request, confirmation.email_address.user, backend='allauth.account.auth_backends.AuthenticationBackend')
        
        messages.success(request, "Successfully logged in via magic link!")
        return redirect('dashboard:index')

    # GET request: render the styled confirmation page
    context = {'confirmation': confirmation, 'key': key}
    return render(request, "account/email_confirm.html", context)


@require_POST
def confirm_email_manual(request):
    """
    Accepts a verification token/key pasted manually by the user
    (for PWA / mobile users who can't click the magic link).
    Delegates to allauth's own confirmation logic so we stay consistent.
    """
    key = request.POST.get('key', '').strip()
    if not key:
        messages.error(request, "Please enter a verification code.")
        return redirect('account_login')

    # Try HMAC-style key first (modern allauth default)
    confirmation = EmailConfirmationHMAC.from_key(key)

    # Fall back to DB-stored confirmation (older / non-HMAC flow)
    if confirmation is None:
        try:
            confirmation = EmailConfirmation.objects.get(key=key.lower())
        except EmailConfirmation.DoesNotExist:
            confirmation = None

    if confirmation is None:
        messages.error(request, "That code is invalid or has expired. Please request a new one.")
        return redirect('account_login')

    try:
        confirmation.confirm(request)
        messages.success(request, "Email confirmed! You are now logged in.")
        return redirect('dashboard:index')
    except Exception:
        messages.error(request, "That code is invalid or has already been used.")
        return redirect('account_login')
