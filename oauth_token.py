import datetime as dt
import os

import custom_requests


class Token:
    def __init__(self, access_token="", refresh_token="", expires_at=""):
        self.access_token = access_token
        self.refresh_token = refresh_token
        try:
            self.expires_at = dt.datetime.fromisoformat(expires_at)
        except (TypeError, ValueError):
            self.expires_at = dt.datetime.now() + dt.timedelta(seconds=int(expires_at))  # expires_in


def ensure_valid_token(token: Token, provider="google"):
    if token.expires_at and dt.datetime.now() < token.expires_at:
        data = custom_requests.get(
            "https://oauth2.googleapis.com/tokeninfo", {"access_token": token.access_token}
        ).json()
        if "error" not in data:
            return

    TOKEN_REFRESH_URLS = {"google": "https://oauth2.googleapis.com/token"}
    PARAMS = {
        "google": {
            "client_id": os.getenv(provider.upper() + "_CLIENT_ID"),
            "client_secret": os.getenv(provider.upper() + "_CLIENT_SECRET"),
            "refresh_token": token.refresh_token,
            "grant_type": "refresh_token",
        }
    }
    token_refresh_url = TOKEN_REFRESH_URLS.get(provider)
    params = PARAMS.get(provider)
    if not token_refresh_url or not params:
        return

    data = custom_requests.post(token_refresh_url, params).json()
    if "error" in data:
        raise ValueError(f"{data.get('error', '')}: {data.get('error_description', '')}")

    token.access_token = data.get("access_token", "")
    expires_in = data.get("expires_in", None)
    if expires_in:
        token.expires_at = dt.datetime.now() + dt.timedelta(seconds=int(expires_in))
