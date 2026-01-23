from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path

from paperless_migration import views

urlpatterns = [
    path("accounts/login/", views.migration_login, name="account_login"),
    path("accounts/", include("allauth.urls")),
    path("migration/", views.migration_home, name="migration_home"),
    path("migration/transform/stream", views.transform_stream, name="transform_stream"),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
