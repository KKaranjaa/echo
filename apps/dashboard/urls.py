from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.dashboard_index, name='index'),

    # Tab management
    path('tabs/create/', views.create_tab, name='create-tab'),
    path('tabs/<uuid:tab_id>/rename/', views.rename_tab, name='rename-tab'),
    path('tabs/<uuid:tab_id>/delete/', views.delete_tab, name='delete-tab'),

    # Session management
    path('sessions/<uuid:session_id>/assign-tab/', views.assign_session_tab, name='assign-session-tab'),
    path('sessions/<uuid:session_id>/delete/', views.delete_session, name='delete-session'),
]
