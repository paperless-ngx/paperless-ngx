from django.utils.translation import gettext_lazy as _

LOGIN_ROUTE_NAME = "account_login"
DISCORD_REDIRECT_ROUTE_NAME = "paperless_discord:callback"
DISCORD_AUTHENTICATION_BACKEND = "paperless_discord.auth.DiscordAuthenticationBackend"
DISCORD_LOGIN_ERROR_ATTR = "discord_login_error"

DISCORD_STATE_SESSION_KEY = "discord_oauth_state"
DISCORD_NEXT_URL_SESSION_KEY = "discord_next_url"
DISCORD_API_TIMEOUT = 10.0
LOCAL_DEV_HOSTS = ("localhost", "127.0.0.1")
DISCORD_TOKEN_PATH = "/oauth2/token"
DISCORD_GUILD_MEMBER_PATH = "/v10/users/@me/guilds/{guild_id}/member"
DISCORD_USER_PATH = "/users/@me"

ERROR_DISCORD_MISSING_CONFIGURATION = _("La configuración de Discord OAuth está incompleta.")
ERROR_DISCORD_INVALID_STATE = _("La respuesta de Discord no es válida. Intenta iniciar sesión nuevamente.")
ERROR_DISCORD_ACCESS_FAILED = _("No se pudo completar el acceso con Discord.")
ERROR_DISCORD_TOKEN_FAILED = _("No se pudo obtener el token de Discord.")
ERROR_DISCORD_PROFILE_FAILED = _("No se pudo leer el perfil de Discord.")
ERROR_DISCORD_MEMBER_REQUIRED = _("Tu cuenta de Discord no pertenece al servidor autorizado.")
ERROR_DISCORD_INVALID_IDENTIFIER = _("La cuenta de Discord no proporcionó un identificador válido.")
ERROR_DISCORD_ALLOWED_ROLES_MISSING = _("La configuración de roles permitidos de Discord está incompleta.")
ERROR_DISCORD_ROLE_REQUIRED = _("No cuentas con los roles necesarios para acceder a este sistema.")
ERROR_DISCORD_AUTH_FAILED = _("Autenticación fallida con Discord.")
