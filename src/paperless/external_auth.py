import base64
import hashlib
import re
import secrets
from typing import Literal
from typing import TypedDict
from typing import cast
from urllib.parse import parse_qsl
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.parse import urlunsplit

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

EXTERNAL_AUTH_FLOW_SESSION_KEY = "external_auth_flow"
EXTERNAL_AUTH_CODE_CACHE_PREFIX = "external_auth_code"
EXTERNAL_AUTH_PKCE_METHOD_S256 = "S256"

_PKCE_VERIFIER_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
_PKCE_S256_CHALLENGE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class ExternalAuthFlow(TypedDict):
    redirect_uri: str
    state: str | None
    code_challenge: str
    code_challenge_method: str


class ExternalAuthCodePayload(TypedDict):
    user_id: int
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str


def external_auth_is_enabled() -> bool:
    return len(settings.EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS) > 0


def is_allowed_redirect_uri(redirect_uri: str) -> bool:
    return redirect_uri in settings.EXTERNAL_AUTH_ALLOWED_REDIRECT_URIS


def validate_code_challenge(
    code_challenge: str,
    code_challenge_method: str,
) -> Literal["unsupported_method", "invalid_code_challenge"] | None:
    if code_challenge_method != EXTERNAL_AUTH_PKCE_METHOD_S256:
        return "unsupported_method"
    if not _PKCE_S256_CHALLENGE_PATTERN.fullmatch(code_challenge):
        return "invalid_code_challenge"
    return None


def is_valid_code_verifier(code_verifier: str) -> bool:
    return bool(_PKCE_VERIFIER_PATTERN.fullmatch(code_verifier))


def build_s256_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def does_pkce_match(
    *,
    code_verifier: str,
    code_challenge: str,
    code_challenge_method: str,
) -> bool:
    if not is_valid_code_verifier(code_verifier):
        return False
    if code_challenge_method != EXTERNAL_AUTH_PKCE_METHOD_S256:
        return False
    return build_s256_code_challenge(code_verifier) == code_challenge


def save_external_auth_flow(
    request,
    *,
    redirect_uri: str,
    state: str | None,
    code_challenge: str,
    code_challenge_method: str,
) -> None:
    request.session[EXTERNAL_AUTH_FLOW_SESSION_KEY] = {
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
        "created_at": int(timezone.now().timestamp()),
    }
    request.session.modified = True


def get_external_auth_flow(request) -> ExternalAuthFlow | None:
    flow = request.session.get(EXTERNAL_AUTH_FLOW_SESSION_KEY)
    if not isinstance(flow, dict):
        return None

    redirect_uri = flow.get("redirect_uri")
    created_at = flow.get("created_at")
    state = flow.get("state")
    code_challenge = flow.get("code_challenge")
    code_challenge_method = flow.get("code_challenge_method")

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

    if not isinstance(code_challenge, str):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if not isinstance(code_challenge_method, str):
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    if validate_code_challenge(code_challenge, code_challenge_method) is not None:
        request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
        request.session.modified = True
        return None

    return {
        "redirect_uri": redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }


def pop_external_auth_flow(request) -> ExternalAuthFlow | None:
    flow = get_external_auth_flow(request)
    if flow is None:
        return None
    request.session.pop(EXTERNAL_AUTH_FLOW_SESSION_KEY, None)
    request.session.modified = True
    return flow


def _external_auth_code_cache_key(code: str) -> str:
    return f"{EXTERNAL_AUTH_CODE_CACHE_PREFIX}:{code}"


def issue_external_auth_code(
    *,
    user_id: int,
    redirect_uri: str,
    code_challenge: str,
    code_challenge_method: str,
) -> str:
    code = secrets.token_urlsafe(32)
    cache.set(
        _external_auth_code_cache_key(code),
        {
            "user_id": user_id,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
        },
        timeout=settings.EXTERNAL_AUTH_CODE_TTL_SECONDS,
    )
    return code


def consume_external_auth_code(code: str) -> ExternalAuthCodePayload | None:
    cached = cache.get(_external_auth_code_cache_key(code))
    if not isinstance(cached, dict):
        return None

    user_id = cached.get("user_id")
    redirect_uri = cached.get("redirect_uri")
    code_challenge = cached.get("code_challenge")
    code_challenge_method = cached.get("code_challenge_method")
    if not isinstance(user_id, int):
        return None
    if not isinstance(redirect_uri, str):
        return None
    if not isinstance(code_challenge, str):
        return None
    if not isinstance(code_challenge_method, str):
        return None

    cache.delete(_external_auth_code_cache_key(code))
    return {
        "user_id": user_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "code_challenge_method": code_challenge_method,
    }


def build_external_auth_callback_url(
    redirect_uri: str,
    *,
    code: str | None = None,
    error: str | None = None,
    state: str | None,
) -> str:
    if (code is None) == (error is None):
        raise ValueError("Exactly one of code or error must be provided")

    parsed = urlsplit(redirect_uri)
    query = parse_qsl(parsed.query, keep_blank_values=True)
    if code is not None:
        query.append(("code", code))
    if error is not None:
        query.append(("error", error))
    if state is not None:
        query.append(("state", state))

    return cast(
        "str",
        urlunsplit(parsed._replace(query=urlencode(query))),
    )
