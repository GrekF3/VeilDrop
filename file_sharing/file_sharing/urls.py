from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('dj_admin/', admin.site.urls),
    path('', include('file_manager.urls')),  # Добавьте это
    path('', include('anon_bot_manager.urls')),
    path('', include('anon_support_manager.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
