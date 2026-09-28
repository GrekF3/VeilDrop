from django.urls import path
from . import views

urlpatterns = [
    path('admin_bot/', views.bot_admin_panel, name='admin_bot'),
    path('admin_bot/broadcast/', views.broadcast_view, name='broadcast'),
    path('admin_bot/manage-users/', views.manage_users_view, name='manage_users'),

]