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

    return render(request, 'dashboard/index.html', {
        'sessions': sessions,
        'tabs': tabs,
        'active_tab': active_tab,
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


@login_required
@require_POST
def delete_session(request, session_id):
    session = get_object_or_404(Session, id=session_id, user=request.user)
    session.delete()
    return JsonResponse({'ok': True})
