from typing import Optional

from allauth.headless.tokens.sessions import SessionTokenStrategy
from django.http import HttpRequest
from rest_framework.authtoken.models import Token


class DrfTokenStrategy(SessionTokenStrategy):
    def create_access_token(self, request: HttpRequest) -> Optional[str]:
        token, _ = Token.objects.get_or_create(user=request.user)
        return token.key
