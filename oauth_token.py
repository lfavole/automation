import datetime as dt
import json
from pathlib import Path

import custom_requests
from get_secrets import get_secret


class Token:
    """An OAuth2 access/refresh token to access a service."""

    def __init__(self, access_token="", refresh_token="", expires_at="", *, provider: str):
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

        self._ensure_valid()

    @property
    def file(self):
        """The file containing the token."""
        return Path(__file__).parent / f"{self.provider}_token.json"

    def save(self):
        """Save the token to its file."""
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
    def from_file(cls, provider: str):
        """Get the token from its file. If it doesn't exist, raise an error."""
        file = Path(__file__).parent / f"{provider}_token.json"
        if not file.exists():
            raise RuntimeError(f"Can't find {provider} token")
        data = json.loads(file.read_text())
        return cls(data["access_token"], data["refresh_token"], data["expires_at"], provider=provider)

    def _ensure_valid(self):
        """Ensure the token is valid by refreshing it if needed."""
        if self.provider == "google" and self.expires_at and dt.datetime.now() > self.expires_at:
            try:
                data = custom_requests.get(
                    "https://oauth2.googleapis.com/tokeninfo", {"access_token": self.access_token}
                ).json()
                return
            except OSError:
                pass

        token_refresh_url = {
            "google": "https://oauth2.googleapis.com/token",
        }.get(self.provider)
        params = {
            "google": {
                "client_id": get_secret(self.provider.upper() + "_CLIENT_ID"),
                "client_secret": get_secret(self.provider.upper() + "_CLIENT_SECRET"),
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        }.get(self.provider)
        if not token_refresh_url or not params:
            return

        try:
            data = custom_requests.post(token_refresh_url, params).json()
        except OSError as err:
            data: dict = err.response.json()  # type: ignore
            raise ValueError(f"{data.get('error', '')}: {data.get('error_description', '')}") from err

        self.access_token = data.get("access_token", "")
        expires_in = data.get("expires_in", None)
        if expires_in:
            self.expires_at = dt.datetime.now() + dt.timedelta(seconds=int(expires_in))

        self.save()
