from django.urls import path
from . import views

urlpatterns = [
    path('', views.chat, name='home'),
    path('chat/', views.chat, name='chat'),
    path('chat/response/', views.get_chatbot_response, name='get_chatbot_response'),
    path('profile/', views.profile, name='profile'),
    path('events/', views.event_list, name='event_list'),
    path('events/create/', views.event_create, name='event_create'),
    path('events/<int:event_id>/', views.event_detail, name='event_detail'),
    path('events/<int:event_id>/update/', views.event_update, name='event_update'),
    path('events/<int:event_id>/delete/', views.event_delete, name='event_delete'),
    path('events/<int:event_id>/write/', views.start_writing_session, name='start_writing_session'),
    path('conversation/<int:conversation_id>/', views.get_conversation, name='get_conversation'),
    path('chat/history/<int:event_id>/<str:phase>/', views.get_phase_history, name='get_phase_history'),
    path('chat/save/', views.save_session, name='save_session'),
    path('api/sessions/<int:event_id>/<str:phase>/', views.get_phase_sessions, name='get_phase_sessions'),
    path('session/<int:session_id>/', views.view_session, name='view_session'),
]
