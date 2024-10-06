from django.conf import settings

# Gmail setup guide: https://postmansmtp.com/how-to-configure-post-smtp-with-gmailgsuite-using-oauth/
# Outlok setup guide: https://medium.com/@manojkumardhakad/python-read-and-send-outlook-mail-using-oauth2-token-and-graph-api-53de606ecfa1


def generate_gmail_oauth_url() -> str:
    token_request_uri = "https://accounts.google.com/o/oauth2/auth"
    response_type = "code"
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    redirect_uri = "http://localhost:8000/api/oauth/callback/"
    scope = "https://mail.google.com/"
    access_type = "offline"
    url = f"{token_request_uri}?response_type={response_type}&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&access_type={access_type}&prompt=consent"
    return url


def generate_outlook_oauth_url() -> str:
    token_request_uri = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    response_type = "code"
    client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
    redirect_uri = "http://localhost:8000/api/oauth/callback/"
    scope = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"
    url = f"{token_request_uri}?response_type={response_type}&response_mode=query&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
    return url


def generate_gmail_token_request_data(code: str) -> dict:
    client_id = settings.GMAIL_OAUTH_CLIENT_ID
    client_secret = settings.GMAIL_OAUTH_CLIENT_SECRET
    scope = "https://mail.google.com/"

    return {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
        "redirect_uri": "http://localhost:8000/api/oauth/callback/",
        "grant_type": "authorization_code",
    }


def generate_outlook_token_request_data(code: str) -> dict:
    client_id = settings.OUTLOOK_OAUTH_CLIENT_ID
    client_secret = settings.OUTLOOK_OAUTH_CLIENT_SECRET
    scope = "offline_access https://outlook.office.com/IMAP.AccessAsUser.All"

    return {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "scope": scope,
        "redirect_uri": "http://localhost:8000/api/oauth/callback/",
        "grant_type": "authorization_code",
    }
