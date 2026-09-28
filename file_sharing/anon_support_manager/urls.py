from django.urls import path
from .views import support_panel_view
from .views import ticket_chat, support_panel_view

urlpatterns = [
    # другие URL
    path('admin_bot/support/', support_panel_view, name='support_panel'),
    path('supports/tickets/chat/<int:ticket_id>/', ticket_chat, name='ticket_chat'),  # Чат с пользователем
]
