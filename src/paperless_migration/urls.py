"""URL configuration for migration mode."""

from __future__ import annotations

from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path

from paperless_migration import views

urlpatterns = [
    path("accounts/login/", views.migration_login, name="account_login"),
    path("accounts/", include("allauth.urls")),
    path("migration/", views.migration_home, name="migration_home"),
    # Redirect root to migration home
    path("", views.migration_home, name="home"),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()
