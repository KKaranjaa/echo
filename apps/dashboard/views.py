from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from apps.uploads.models import Session
from .models import Tab
import json


@login_required
def dashboard_index(request):
    sessions = Session.objects.filter(user=request.user).order_by('-created_at')
    tabs = request.user.tabs.all()

    active_tab_id = request.GET.get('tab')
    active_tab = None

    if active_tab_id:
        try:
            active_tab = tabs.get(id=active_tab_id)
            sessions = sessions.filter(tab=active_tab)
        except Tab.DoesNotExist:
            pass

    # Check if the user has at least one verified email address
    email_verified = request.user.emailaddress_set.filter(verified=True).exists()

    return render(request, 'dashboard/index.html', {
        'sessions': sessions,
        'tabs': tabs,
        'active_tab': active_tab,
        'email_verified': email_verified,
    })


@login_required
@require_POST
def create_tab(request):
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    tab, created = Tab.objects.get_or_create(user=request.user, name=name)
    return JsonResponse({'id': str(tab.id), 'name': tab.name, 'created': created})


@login_required
@require_POST
def rename_tab(request, tab_id):
    tab = get_object_or_404(Tab, id=tab_id, user=request.user)
    data = json.loads(request.body)
    name = data.get('name', '').strip()
    if not name:
        return JsonResponse({'error': 'Name required'}, status=400)
    tab.name = name
    tab.save()
    return JsonResponse({'id': str(tab.id), 'name': tab.name})


@login_required
@require_POST
def delete_tab(request, tab_id):
    tab = get_object_or_404(Tab, id=tab_id, user=request.user)
    tab.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def assign_session_tab(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    data = json.loads(request.body)
    tab_id = data.get('tab_id')
    if tab_id:
        tab = get_object_or_404(Tab, id=tab_id, user=request.user)
        session.tab = tab
    else:
        session.tab = None
    session.save()
    return JsonResponse({'ok': True})


import os
import shutil
from django.contrib.auth import logout
from django.conf import settings

@login_required
@require_POST
def delete_session(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    session.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def delete_account(request):
    user = request.user

    # 1. Clean up media directories for all sessions owned by this user
    user_sessions = Session.objects.filter(user=user)
    for session in user_sessions:
        upload_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', str(session.id))
        if os.path.exists(upload_dir):
            try:
                shutil.rmtree(upload_dir, ignore_errors=True)
            except Exception:
                pass

    # 2. Log out the user
    logout(request)

    # 3. Permanently delete the user model (cascades to sessions, transcripts, summaries, tabs, email records)
    user.delete()

    return JsonResponse({'ok': True, 'redirect': '/'})
