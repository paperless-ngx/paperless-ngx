from django.urls import include
from django.urls import path

from paperless_migration import views

urlpatterns = [
    path("accounts/login/", views.migration_login, name="account_login"),
    path("accounts/", include("allauth.urls")),
    path("migration/", views.migration_home, name="migration_home"),
]
