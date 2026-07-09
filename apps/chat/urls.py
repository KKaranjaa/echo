from django.urls import path
from .views import chat_api, chat_page

urlpatterns = [
    path('', chat_page, name='chat_page'),
    path('<uuid:session_id>/', chat_api, name='chat_api'),
]
