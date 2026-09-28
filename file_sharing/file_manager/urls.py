from django.urls import path
from django.shortcuts import reverse
from django.contrib.sitemaps import Sitemap
from django.contrib.sitemaps.views import sitemap
from . import views


class StaticViewSitemap(Sitemap):
    priority = 1.0
    changefreq = 'monthly'

    def items(self):
        return ['home']  # название вашего URL

    def location(self, item):
        return reverse(item)

sitemaps = {
    'static': StaticViewSitemap,
}


urlpatterns = [
    path('', views.home, name='home'),
    path('file/<str:key>/', views.file_view, name='file_view'),
    path('upload/', views.upload_file, name='upload'),
    path('upload/success/', views.upload_success_view, name='upload_success'),
    path('download/<str:key>/', views.download_file, name='file_download'),
    path('check-upload-status/', views.check_upload_status, name='check_upload_status'),
    path('check-file-load-status/', views.check_load_status, name='check_load_status'),
    path("robots.txt", views.robots_txt, name="robots_txt"),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('restore.php', views.restopre_php_page, name='restore_php'),
]