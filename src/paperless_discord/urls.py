from django.urls import path

from . import views

app_name = "paperless_discord"

urlpatterns = [
    path("accounts/discord/login/", views.DiscordSignInView.as_view(), name="login"),
    path("accounts/discord/login/callback/", views.DiscordCallbackView.as_view(), name="callback"),
]
