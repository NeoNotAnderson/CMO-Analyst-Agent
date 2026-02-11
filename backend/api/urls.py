"""
API URL Configuration
"""

from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Authentication endpoints
    path('auth/login/', views.login_view, name='login'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('auth/me/', views.get_current_user, name='current_user'),

    # Session endpoints
    path('session/initialize/', views.initialize_session, name='initialize_session'),
    path('session/active-prospectus/', views.set_active_prospectus_view, name='set_active_prospectus'),

    # Prospectus endpoints
    path('prospectus/upload/', views.upload_prospectus, name='upload_prospectus'),
    path('prospectus/list/', views.get_prospectus_list, name='prospectus_list'),
    path('prospectus/<uuid:prospectus_id>/status/', views.get_prospectus_status, name='prospectus_status'),

    # Chat endpoints
    path('chat/message/', views.send_chat_message, name='chat_message'),
    path('chat/history/<uuid:prospectus_id>/', views.get_chat_history, name='chat_history'),
    path('chat/history/<uuid:prospectus_id>/clear/', views.clear_chat_history, name='clear_chat_history'),
]
