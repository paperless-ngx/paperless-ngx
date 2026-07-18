from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from importlib import import_module
from typing import TYPE_CHECKING
from typing import Any
from urllib.parse import urlencode

from allauth.account import views as allauth_account_views
from django.conf import settings
from django.contrib import auth
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.auth import HASH_SESSION_KEY
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.http import HttpResponseRedirect
from django.http import JsonResponse
from django.middleware.csrf import rotate_token
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import GenericAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from paperless.models import AccountSession
from paperless.models import AccountSessionAddChallenge
from paperless.models import AccountSessionGroup

if TYPE_CHECKING:
    from collections.abc import Callable
    from datetime import datetime

    from django.contrib.auth.models import User
    from django.contrib.sessions.backends.base import SessionBase
    from django.http import HttpRequest
    from django.http import HttpResponse


ACCOUNT_SESSION_COOKIE_SUFFIX = "account_sessions"
ADD_CHALLENGE_SESSION_KEY = "paperless_account_session_add_challenge"
MAX_ACCOUNT_SESSIONS = 10


class AccountSessionLimitError(Exception):
    """Raised when a browser profile reaches its saved-account limit."""


def switching_enabled() -> bool:
    """Return whether the configured authentication mode supports switching."""

    return not settings.AUTO_LOGIN_USERNAME and (
        "paperless.auth.HttpRemoteUserMiddleware" not in settings.MIDDLEWARE
    )


def account_session_cookie_name() -> str:
    """Return the configured name of the browser-profile group cookie."""

    return f"{settings.COOKIE_PREFIX}{ACCOUNT_SESSION_COOKIE_SUFFIX}"


def _token_digest(token: str) -> str:
    """Hash a browser-profile token before database lookup or storage."""

    return hashlib.sha256(token.encode()).hexdigest()


def group_from_request(request: HttpRequest) -> AccountSessionGroup | None:
    """Resolve the account-session group referenced by the request cookie."""

    token = request.COOKIES.get(account_session_cookie_name())
    if not token:
        return None
    return AccountSessionGroup.objects.filter(token_digest=_token_digest(token)).first()


def create_group() -> tuple[AccountSessionGroup, str]:
    """Create an account-session group and return its plaintext cookie token."""

    token = secrets.token_urlsafe(32)
    group = AccountSessionGroup.objects.create(token_digest=_token_digest(token))
    return group, token


def set_group_cookie(response: HttpResponse, token: str) -> None:
    """Attach the protected account-session group cookie to a response."""

    persistent = not settings.SESSION_EXPIRE_AT_BROWSER_CLOSE
    response.set_cookie(
        account_session_cookie_name(),
        token,
        max_age=settings.SESSION_COOKIE_AGE if persistent else None,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=True,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def clear_group_cookie(response: HttpResponse) -> None:
    """Remove the account-session group cookie from the browser."""

    response.delete_cookie(
        account_session_cookie_name(),
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def _session_store(session_key: str) -> SessionBase:
    """Open a session through the configured Django session backend."""

    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore(session_key=session_key)


def delete_session(session_key: str | None) -> None:
    """Invalidate a session in every layer of the configured backend."""

    if session_key:
        # Use the configured backend so cached_db removes both its database
        # row and cached copy. Deleting Session directly would leave the
        # cached credential usable until it expired.
        _session_store(session_key).delete()


def create_anonymous_session(challenge_id: str) -> SessionBase:
    """Create the temporary anonymous session used to add an account."""

    engine = import_module(settings.SESSION_ENGINE)
    session = engine.SessionStore()
    session[ADD_CHALLENGE_SESSION_KEY] = challenge_id
    session.set_expiry(
        0 if settings.SESSION_EXPIRE_AT_BROWSER_CLOSE else settings.SESSION_COOKIE_AGE,
    )
    session.create()
    return session


def set_session_cookie(response: HttpResponse, session: SessionBase) -> None:
    """Activate a stored Django session by setting its browser cookie."""

    if session.get_expire_at_browser_close():
        max_age = None
    else:
        expiry = Session.objects.filter(session_key=session.session_key).values_list(
            "expire_date",
            flat=True,
        ).first()
        max_age = max(
            0,
            int(
                (
                    (expiry or session.get_expiry_date()) - timezone.now()
                ).total_seconds(),
            ),
        )
    response.set_cookie(
        settings.SESSION_COOKIE_NAME,
        session.session_key,
        max_age=max_age,
        path=settings.SESSION_COOKIE_PATH,
        domain=settings.SESSION_COOKIE_DOMAIN,
        secure=settings.SESSION_COOKIE_SECURE,
        httponly=settings.SESSION_COOKIE_HTTPONLY,
        samesite=settings.SESSION_COOKIE_SAMESITE,
    )


def _session_hash_is_valid(user: User, session_hash: str | None) -> bool:
    """Check a session hash against the user's current and fallback hashes."""

    if not session_hash:
        return False
    if constant_time_compare(user.get_session_auth_hash(), session_hash):
        return True
    return any(
        constant_time_compare(fallback_hash, session_hash)
        for fallback_hash in user.get_session_auth_fallback_hash()
    )


def validate_account_session(
    account_session: AccountSession,
) -> tuple[User, SessionBase] | None:
    """Validate an enrolled session and return its user and session store."""

    session_row = Session.objects.filter(
        session_key=account_session.session_key,
        expire_date__gt=timezone.now(),
    ).first()
    if session_row is None:
        return None

    session = _session_store(account_session.session_key)
    data = session.load()
    try:
        session_user_id = int(data[SESSION_KEY])
    except (KeyError, TypeError, ValueError):
        return None
    if session_user_id != account_session.user_id:
        return None
    if data.get(BACKEND_SESSION_KEY) not in settings.AUTHENTICATION_BACKENDS:
        return None

    user = account_session.user
    if not user.is_active or not _session_hash_is_valid(
        user,
        data.get(HASH_SESSION_KEY),
    ):
        return None
    return user, session


def prune_group(group: AccountSessionGroup) -> list[AccountSession]:
    """Delete invalid enrolled sessions and return the valid memberships."""

    valid: list[AccountSession] = []
    for account_session in group.account_sessions.select_related("user"):
        if validate_account_session(account_session) is None:
            delete_session(account_session.session_key)
            account_session.delete()
        else:
            valid.append(account_session)
    return valid


def register_session(
    group: AccountSessionGroup,
    user: User,
    session_key: str,
    *,
    evict_if_full: bool = False,
) -> AccountSession:
    """Enroll a user's Django session in a browser-profile group."""

    existing = group.account_sessions.filter(user=user).first()
    if existing is not None:
        if existing.session_key != session_key:
            delete_session(existing.session_key)
            existing.session_key = session_key
            existing.save(update_fields=("session_key", "last_used"))
        return existing

    valid = prune_group(group)
    if len(valid) >= MAX_ACCOUNT_SESSIONS:
        if not evict_if_full:
            raise AccountSessionLimitError
        oldest = min(valid, key=lambda item: item.last_used)
        delete_session(oldest.session_key)
        oldest.delete()

    return AccountSession.objects.create(
        group=group,
        user=user,
        session_key=session_key,
    )


def current_membership(
    request: HttpRequest,
    group: AccountSessionGroup,
) -> AccountSession | None:
    """Return the enrollment matching the request's current user and session."""

    session_key = request.session.session_key
    if not request.user.is_authenticated or not session_key:
        return None
    return group.account_sessions.filter(
        user=request.user,
        session_key=session_key,
    ).first()


def can_enroll_changed_session(
    request: HttpRequest,
    group: AccountSessionGroup,
    incoming_session_key: str | None,
) -> bool:
    """Check whether a changed session is authorized to join the group."""

    if incoming_session_key and group.account_sessions.filter(
        session_key=incoming_session_key,
    ).exists():
        return True

    return has_active_add_challenge(request, group)


def has_active_add_challenge(
    request: HttpRequest,
    group: AccountSessionGroup,
) -> bool:
    """Return whether the request carries a valid add-account challenge."""

    challenge_id = request.session.get(ADD_CHALLENGE_SESSION_KEY)
    return bool(
        challenge_id
        and AccountSessionAddChallenge.objects.filter(
            pk=challenge_id,
            group=group,
            expires__gt=timezone.now(),
        ).exists(),
    )


def delete_membership(account_session: AccountSession) -> None:
    """Delete an enrollment and invalidate its underlying Django session."""

    delete_session(account_session.session_key)
    account_session.delete()


def delete_group_if_empty(group: AccountSessionGroup) -> bool:
    """Delete an account-session group when it has no remaining accounts."""

    if group.account_sessions.exists():
        return False
    group.delete()
    return True


def get_add_challenge_expiry() -> datetime:
    """Return the expiry time for a newly created add-account challenge."""

    return timezone.now() + timedelta(minutes=10)


def _activate_most_recent(
    response: HttpResponse,
    group: AccountSessionGroup,
    request: Any | None = None,
) -> AccountSession | None:
    """Activate the most recently used valid account remaining in a group."""

    valid = sorted(
        prune_group(group),
        key=lambda item: item.last_used,
        reverse=True,
    )
    if not valid:
        return None
    target = valid[0]
    validated = validate_account_session(target)
    if validated is None:  # pragma: no cover - prune_group already checked it
        return None
    _, session = validated
    target.save(update_fields=("last_used",))
    if request is not None:
        # Authentication logout flushes request.session. Replacing it prevents
        # SessionMiddleware from deleting the replacement cookie on response.
        django_request = getattr(request, "_request", request)
        django_request.session = session
    set_session_cookie(response, session)
    return target


def _redirect_with_switch_marker(*, reason: str | None = None) -> str:
    """Build the post-switch redirect with an optional notification reason."""

    separator = "&" if "?" in settings.LOGIN_REDIRECT_URL else "?"
    redirect_url = f"{settings.LOGIN_REDIRECT_URL}{separator}account_switched=1"
    if reason is not None:
        redirect_url = f"{redirect_url}&{urlencode({'account_switch_reason': reason})}"
    return redirect_url


class AccountSessionsView(GenericAPIView[Any]):
    """List the accounts enrolled for the current browser profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(responses={(200, "application/json"): OpenApiTypes.OBJECT})
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Return valid enrolled accounts and identify the active account."""

        if not switching_enabled():
            return Response({"enabled": False, "accounts": []})
        group = group_from_request(request)
        if group is None:
            if not request.session.session_key:
                return Response({"enabled": False, "accounts": []})
            return Response(
                {
                    "enabled": True,
                    "accounts": [
                        {
                            "id": request.user.pk,
                            "username": request.user.username,
                            "first_name": request.user.first_name,
                            "last_name": request.user.last_name,
                            "current": True,
                            "last_used": timezone.now(),
                        },
                    ],
                },
            )
        if current_membership(request, group) is None:
            return Response(
                {"detail": "The current browser session is not enrolled."},
                status=status.HTTP_409_CONFLICT,
            )

        current_key = request.session.session_key
        accounts = [
            {
                "id": account_session.user_id,
                "username": account_session.user.username,
                "first_name": account_session.user.first_name,
                "last_name": account_session.user.last_name,
                "current": account_session.session_key == current_key,
                "last_used": account_session.last_used,
            }
            for account_session in sorted(
                prune_group(group),
                key=lambda item: item.last_used,
                reverse=True,
            )
        ]
        return Response({"enabled": True, "accounts": accounts})


class AccountSessionAddView(GenericAPIView[Any]):
    """Start the authentication flow for adding another account."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Create an add challenge and redirect to an anonymous login session."""

        if not switching_enabled():
            return Response(
                {"detail": "Account switching is unavailable for this login mode."},
                status=status.HTTP_409_CONFLICT,
            )
        group = group_from_request(request)
        if group is None or current_membership(request, group) is None:
            return Response(
                {"detail": "The current browser session is not enrolled."},
                status=status.HTTP_409_CONFLICT,
            )
        if len(prune_group(group)) >= MAX_ACCOUNT_SESSIONS:
            return Response(
                {
                    "detail": (
                        f"A maximum of {MAX_ACCOUNT_SESSIONS} accounts is allowed."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        AccountSessionAddChallenge.objects.filter(group=group).delete()
        challenge = AccountSessionAddChallenge.objects.create(
            group=group,
            previous_session_key=request.session.session_key,
            expires=get_add_challenge_expiry(),
        )
        anonymous_session = create_anonymous_session(str(challenge.pk))
        complete_url = reverse("account_switch_complete")
        login_url = f"{reverse('account_login')}?{urlencode({'next': complete_url})}"
        response = Response({"redirect_url": login_url})
        set_session_cookie(response, anonymous_session)
        return response


class AccountSessionSwitchView(GenericAPIView[Any]):
    """Switch the browser to a previously enrolled account session."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request={
            "application/json": {
                "type": "object",
                "properties": {"user_id": {"type": "integer"}},
                "required": ["user_id"],
            },
        },
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Validate and activate the requested enrolled account session."""

        if not switching_enabled():
            return Response(
                {"detail": "Account switching is unavailable for this login mode."},
                status=status.HTTP_409_CONFLICT,
            )
        group = group_from_request(request)
        if group is None or current_membership(request, group) is None:
            return Response(
                {"detail": "The current browser session is not enrolled."},
                status=status.HTTP_409_CONFLICT,
            )
        try:
            user_id = int(request.data.get("user_id"))
        except (TypeError, ValueError):
            return Response(
                {"detail": "A valid user_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target = (
            group.account_sessions.select_related("user")
            .filter(user_id=user_id)
            .first()
        )
        if target is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        validated = validate_account_session(target)
        if validated is None:
            delete_membership(target)
            return Response(
                {"detail": "That account session is no longer valid."},
                status=status.HTTP_410_GONE,
            )

        _, session = validated
        target.save(update_fields=("last_used",))
        rotate_token(request)
        response = Response({"redirect_url": _redirect_with_switch_marker()})
        set_session_cookie(response, session)
        return response


class AccountSessionRemoveView(GenericAPIView[Any]):
    """Remove an account from the browser's quick-switch group."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def delete(
        self,
        request: Any,
        user_id: int,
        *args: Any,
        **kwargs: Any,
    ) -> Response:
        """Invalidate and remove the requested account enrollment."""

        if not switching_enabled():
            return Response(
                {"detail": "Account switching is unavailable for this login mode."},
                status=status.HTTP_409_CONFLICT,
            )
        group = group_from_request(request)
        if group is None or current_membership(request, group) is None:
            return Response(status=status.HTTP_409_CONFLICT)
        membership = group.account_sessions.filter(user_id=user_id).first()
        if membership is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        is_current = membership.session_key == request.session.session_key
        if is_current:
            auth.logout(request)
        delete_membership(membership)

        response = Response({"redirect_url": settings.LOGOUT_REDIRECT_URL})
        if (
            is_current
            and _activate_most_recent(response, group, request=request) is not None
        ):
            response.data["redirect_url"] = _redirect_with_switch_marker(
                reason="logout",
            )
        if delete_group_if_empty(group):
            clear_group_cookie(response)
        return response


class AccountSessionLogoutCurrentView(GenericAPIView[Any]):
    """Log out the active account while preserving remaining accounts."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Log out the current account and activate a remaining account."""

        group = group_from_request(request) if switching_enabled() else None
        membership = current_membership(request, group) if group is not None else None

        auth.logout(request)
        if membership is not None:
            delete_membership(membership)

        response = Response({"redirect_url": settings.LOGOUT_REDIRECT_URL})
        if (
            group is not None
            and membership is not None
            and _activate_most_recent(response, group, request=request) is not None
        ):
            response.data["redirect_url"] = _redirect_with_switch_marker(
                reason="logout",
            )

        if group is None or membership is None or delete_group_if_empty(group):
            clear_group_cookie(response)
        return response


class AccountSessionLogoutAllView(GenericAPIView[Any]):
    """Log out every account enrolled for the current browser profile."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=None,
        responses={(200, "application/json"): OpenApiTypes.OBJECT},
    )
    def post(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Invalidate all enrolled sessions and remove their group."""

        if not switching_enabled():
            return Response(
                {"detail": "Account switching is unavailable for this login mode."},
                status=status.HTTP_409_CONFLICT,
            )
        group = group_from_request(request)
        if group is not None and current_membership(request, group) is not None:
            session_keys = group.account_sessions.values_list("session_key", flat=True)
            for session_key in session_keys:
                delete_session(session_key)
            group.delete()
        auth.logout(request)
        response = Response({"redirect_url": settings.LOGOUT_REDIRECT_URL})
        clear_group_cookie(response)
        return response


class AccountSessionCompleteView(View):
    """Complete an add-account challenge after successful authentication."""

    def get(self, request: Any, *args: Any, **kwargs: Any) -> HttpResponse:
        """Enroll the authenticated session and finish the add flow."""

        if not request.user.is_authenticated:
            return redirect(settings.LOGIN_URL)
        challenge_id = request.session.get(ADD_CHALLENGE_SESSION_KEY)
        group = group_from_request(request)
        session_key = request.session.session_key
        if not challenge_id or group is None or not session_key:
            return redirect(settings.LOGIN_REDIRECT_URL)
        challenge = AccountSessionAddChallenge.objects.filter(
            pk=challenge_id,
            group=group,
            expires__gt=timezone.now(),
        ).first()
        if challenge is None:
            return redirect(settings.LOGIN_REDIRECT_URL)
        try:
            register_session(group, request.user, session_key)
        except AccountSessionLimitError:
            challenge.delete()
            return redirect(settings.LOGIN_REDIRECT_URL)
        challenge.delete()
        request.session.pop(ADD_CHALLENGE_SESSION_KEY, None)
        return redirect(_redirect_with_switch_marker())


@require_http_methods(["POST"])
@csrf_protect
def cancel_account_session_add(request: HttpRequest) -> HttpResponse:
    """Cancel adding an account and restore the previously active session."""

    challenge_id = request.session.get(ADD_CHALLENGE_SESSION_KEY)
    group = group_from_request(request)
    if not challenge_id or group is None:
        return redirect(settings.LOGIN_URL)
    challenge = AccountSessionAddChallenge.objects.filter(
        pk=challenge_id,
        group=group,
        expires__gt=timezone.now(),
    ).first()
    if challenge is None:
        return redirect(settings.LOGIN_URL)

    previous = group.account_sessions.select_related("user").filter(
        session_key=challenge.previous_session_key,
    ).first()
    challenge.delete()
    response = HttpResponseRedirect(settings.LOGIN_REDIRECT_URL)
    if previous is not None:
        validated = validate_account_session(previous)
        if validated is not None:
            _, session = validated
            set_session_cookie(response, session)
    delete_session(request.session.session_key)
    request.session.modified = False
    return response


def account_session_logout(request: HttpRequest) -> HttpResponse:
    """Wrap allauth logout to activate a remaining enrolled account safely."""

    if not switching_enabled():
        return allauth_account_views.logout(request)
    group = group_from_request(request)
    session_key = request.session.session_key
    was_authenticated = request.user.is_authenticated
    membership = (
        group.account_sessions.filter(
            session_key=session_key,
            user=request.user,
        ).first()
        if group is not None and session_key and was_authenticated
        else None
    )
    add_challenge_active = bool(
        group is not None and has_active_add_challenge(request, group),
    )
    response = allauth_account_views.logout(request)
    if (
        not was_authenticated
        or request.user.is_authenticated
        or group is None
        or not session_key
        or membership is None
    ):
        if (
            group is not None
            and membership is None
            and not add_challenge_active
        ):
            clear_group_cookie(response)
        return response

    membership.delete()
    switched_response = HttpResponseRedirect(
        _redirect_with_switch_marker(reason="logout"),
    )
    if (
        _activate_most_recent(switched_response, group, request=request)
        is not None
    ):
        return switched_response
    delete_group_if_empty(group)
    clear_group_cookie(response)
    return response


class AccountSessionMiddleware:
    """Enroll browser sessions and reject stale Angular tabs safely."""

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        """Store the next middleware or view callable."""

        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """Reject stale tabs and enroll newly authenticated sessions."""

        expected_user = request.headers.get("X-Paperless-User-ID")
        if (
            switching_enabled()
            and expected_user
            and request.path.startswith(f"{settings.BASE_URL}api/")
            and request.user.is_authenticated
            and expected_user != str(request.user.pk)
        ):
            return JsonResponse(
                {
                    "detail": "The active account changed in another tab.",
                    "code": "account_session_changed",
                },
                status=409,
            )

        incoming_group_token = request.COOKIES.get(account_session_cookie_name())
        group = group_from_request(request) if switching_enabled() else None
        response = self.get_response(request)

        incoming_session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
        current_session_key = request.session.session_key
        if (
            switching_enabled()
            and request.user.is_authenticated
            and current_session_key
            and (
                group is None
                or incoming_session_key != current_session_key
            )
        ):
            cookie_token = None
            if group is not None and not can_enroll_changed_session(
                request,
                group,
                incoming_session_key,
            ):
                group = None
            if group is None:
                group, cookie_token = create_group()
            elif incoming_group_token is not None:
                # A newly authenticated account may outlive the original
                # account, so keep the browser-group cookie aligned with it.
                cookie_token = incoming_group_token
            try:
                register_session(
                    group,
                    request.user,
                    current_session_key,
                    evict_if_full=True,
                )
            except AccountSessionLimitError:  # pragma: no cover
                pass
            if cookie_token is not None:
                set_group_cookie(response, cookie_token)

        return response
