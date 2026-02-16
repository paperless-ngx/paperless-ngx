import secrets
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

EXTERNAL_AUTH_FLOW_SESSION_KEY = "external_auth_flow"
EXTERNAL_AUTH_CODE_CACHE_PREFIX = "external_auth_code"


def external_auth_is_enabled() -> bool:
    return len(settings.EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS) > 0


def is_allowed_redirect_uri(redirect_uri: str) -> bool:
    return redirect_uri in settings.EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS


def save_external_auth_flow(request, *, redirect_uri: str, state: str | None) -> None:
    request.session[EXTERNAL_AUTH_FLOW_SESSION_KEY] = {
        "redirect_uri": redirect_uri,
        "state": state,
        "created_at": int(timezone.now().timestamp()),
    }
    request.session.modified = True


def get_external_auth_flow(request):
    flow = request.session.get(EXTERNAL_AUTH_FLOW_SESSION_KEY)
    if not isinstance(flow, dict):
        return None

    redirect_uri = flow.get("redirect_uri")
    created_at = flow.get("created_at")
    state = flow.get("state")

    if not isinstance(redirect_uri, str):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if not is_allowed_redirect_uri(redirect_uri):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if not isinstance(created_at, int):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if (
        int(timezone.now().timestamp()) - created_at
        > settings.EXTERNAL_AUTH_FLOW_TTL_SECONDS
    ):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if state is not None and not isinstance(state, str):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    return {
        "redirect_uri": redirect_uri,
        "state": state,
    }


def pop_external_auth_flow(request):
    flow = get_external_auth_flow(request)
    if flow is None:
        return None
    request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
    request.session.modified = True
    return flow


def _external_auth_code_cache_key(code: str) -> str:
    return f"{EXTERNAL_AUTH_CODE_CACHE_PREFIX}:{code}"


def issue_external_auth_code(user_id: int) -> str:
    code = secrets.token_urlsafe(32)
    cache.set(
        _external_auth_code_cache_key(code),
        {"user_id": user_id},
        timeout=settings.EXTERNAL_AUTH_CODE_TTL_SECONDS,
    )
    return code


def consume_external_auth_code(code: str) -> int | None:
    cached = cache.get(_external_auth_code_cache_key(code))
    if not isinstance(cached, dict):
        return None

    cache.delete(_external_auth_code_cache_key(code))
    user_id = cached.get("user_id")
    if isinstance(user_id, int):
        return user_id
    return None


def build_external_auth_callback_url(
    redirect_uri: str,
    *,
    code: str,
    state: str | None,
) -> str:
    parsed = urlsplit(redirect_uri)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    query.append(("code", code))
    if state is not None:
        query.append(("state", state))

    return urlunsplit(parsed._replace(query=urlencode(query)))
