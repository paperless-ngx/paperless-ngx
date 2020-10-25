from rest_framework.authentication import TokenAuthentication

# This authentication method is required to serve documents and thumbnails for the front end.
# https://stackoverflow.com/questions/29433416/token-in-query-string-with-django-rest-frameworks-tokenauthentication
class QueryTokenAuthentication(TokenAuthentication):
    def authenticate(self, request):
        # Check if 'token_auth' is in the request query params.
        if 'auth_token' in request.query_params and 'HTTP_AUTHORIZATION' not in request.META:
            return self.authenticate_credentials(request.query_params.get('auth_token'))
        else:
            return None
