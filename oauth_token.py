import datetime as dt
import json
import os
from pathlib import Path

import custom_requests


class Token:
    def __init__(self, access_token="", refresh_token="", expires_at="", provider="google"):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.provider = provider

        if expires_at:
            try:
                self.expires_at = dt.datetime.fromisoformat(expires_at)
            except (TypeError, ValueError):
                self.expires_at = dt.datetime.now() + dt.timedelta(seconds=int(expires_at))  # expires_in
        else:
            self.expires_at = None

    @property
    def file(self):
        return Path(__file__).parent / f"{self.provider}_token.json"

    def save(self):
        self.file.write_text(
            json.dumps(
                {
                    "access_token": self.access_token,
                    "refresh_token": self.refresh_token,
                    "expires_at": str(self.expires_at) if self.expires_at else None,
                }
            )
        )

    @classmethod
    def from_file(cls, provider="google"):
        file = Path(__file__).parent / f"{provider}_token.json"
        if not file.exists():
            return None
        data = json.loads(file.read_text())
        return cls(data["access_token"], data["refresh_token"], data["expires_at"])

    def ensure_valid(self, provider="google"):
        if self.expires_at and dt.datetime.now() < self.expires_at:
            data = custom_requests.get(
                "https://oauth2.googleapis.com/tokeninfo", {"access_token": self.access_token}
            ).json()
            if "error" not in data:
                return

        TOKEN_REFRESH_URLS = {"google": "https://oauth2.googleapis.com/token"}
        PARAMS = {
            "google": {
                "client_id": os.getenv(provider.upper() + "_CLIENT_ID"),
                "client_secret": os.getenv(provider.upper() + "_CLIENT_SECRET"),
                "refresh_token": self.refresh_token,
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

        self.access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", None)
        if expires_in:
            self.expires_at = dt.datetime.now() + dt.timedelta(seconds=int(expires_in))
