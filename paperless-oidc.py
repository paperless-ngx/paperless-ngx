# /// script
# dependencies = [
#   "requests",
#   "authlib",
# ]
# ///
#
# A less shitty python script to demonstrate an oidc flow using allauth-headless and paperless-ngx

import threading
import urllib
import webbrowser
from http.server import BaseHTTPRequestHandler
from http.server import HTTPServer

import requests
from authlib.common.security import generate_token
from authlib.integrations.requests_client import OAuth2Session
from urllib.parse import urlparse, parse_qs

"""
Ignore this, it's just to capture the callback
"""


class RequestHandler(BaseHTTPRequestHandler):
    captured_params = None  # Store the captured parameters

    def do_GET(self):
        if self.path.startswith("/callback"):
            # Parse query parameters
            parsed_url = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed_url.query)
            RequestHandler.captured_params = params

            # Respond to the request
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Parameters captured. You can close this page.")

            # Stop the server after capturing the parameters
            threading.Thread(target=self.server.shutdown).start()


def run_server(port=9000):
    server = HTTPServer(("localhost", port), RequestHandler)
    print(f"Server listening on http://localhost:{port}/callback")
    server.serve_forever()
    return RequestHandler.captured_params


"""
Query providers from paperless
"""
PAPERLESS_URL = "http://localhost:8000/"

# Obtain CSRF Token from main site
session = requests.Session()
initial = session.get(PAPERLESS_URL + "accounts/login")
cookies = initial.cookies
print("CSRF: " + cookies["csrftoken"])

# Request headless config for provider id
response = session.get(PAPERLESS_URL + "_allauth/app/v1/config")
print("Headless config: ", response.json())

# Select the first provider from the response
provider = response.json()["data"]["socialaccount"]["providers"][0]
print("Provider config: ", provider)


"""
Obtain redirect uri from _allauth/browser/v1/auth/provider/redirect
"""
redirect = session.post(
    f"{PAPERLESS_URL}/_allauth/browser/v1/auth/provider/redirect",
    headers={"X-CSRFToken": cookies["csrftoken"]},
    data={
        "provider": provider["id"],
        # My understanding is this is the redirect URL that allauth will
        # redirect to after the OIDC login is completed
        "callback_url": "http://localhost:8000/",
        "process": "login",
        "csrfmiddlewaretoken": cookies["csrftoken"],
    },
    cookies=cookies,
    allow_redirects=False,
)
print("Redirect status code: ", redirect.status_code)

"""
Parse authorization url
"""
parsed_url = urlparse(redirect.headers.get("Location"))
query_params = parse_qs(parsed_url.query)

# Extract scope parameter to match provider
scope_param = query_params["scope"][0]
print("Parsed scopes: ", scope_param)

# Redirect URI from the app
redirect_uri = "http://localhost:9000/callback/"

# Get well-known discovery URL from allauth
discovery_url = provider["openid_configuration_url"]
print(discovery_url)

# Use oidc discovery to get endpoints
oidc_config = requests.get(discovery_url).json()

# Create a new oidc client (Using a library) with PKCE
client = OAuth2Session(
    provider["client_id"],
    redirect_uri=redirect_uri,
    scope=scope_param,
    code_challenge_method="S256",
)

# Create a new authorization URL
code_verifier = generate_token(48)
authorization_url, state = client.create_authorization_url(
    oidc_config["authorization_endpoint"], code_verifier=code_verifier
)

# 1. Redirect the user to the updated URL
webbrowser.open(authorization_url)

# 2. Capture the callback
server_thread = threading.Thread(target=run_server, kwargs={"port": 9000})
server_thread.start()
# Wait for the request and continue execution
while RequestHandler.captured_params is None:
    pass  # Wait for parameters to be captured

print("Captured Parameters:", RequestHandler.captured_params)

# Check state parameter
if state != RequestHandler.captured_params["state"][0]:
    raise Exception("Invalid state")

# Parse authorization code from callback url
authorization_code = RequestHandler.captured_params["code"][0]
print("Authorization code: ", authorization_code)

# 5. Exchange the authorization code for the ID Token
token_response = client.fetch_token(
    oidc_config["token_endpoint"],
    auth=None,
    code=authorization_code,
    code_verifier=code_verifier,
)
id_token = token_response["id_token"]
print("ID Token: ", id_token)

"""
Pass the ID Token to Django allauth
"""

# TODO: This will fail if the user hasn't logged in using OIDC before!

response = session.post(
    PAPERLESS_URL + "_allauth/app/v1/auth/provider/token",
    headers={
        "X-CSRFToken": cookies["csrftoken"],
    },
    json={
        "provider": provider["id"],
        "process": "login",
        "token": {"client_id": provider["client_id"], "id_token": id_token},
        "csrfmiddlewaretoken": cookies["csrftoken"],
    },
)

print("Exchange status code: ", response.status_code)
print("Exchange response: ", response.json())
api_token = response.json()["meta"]["access_token"]
print("Paperless API Token: ", api_token)
