"""Utility functions to manage OAuth access/refresh tokens."""

from pathlib import Path

import custom_requests
from get_secrets import secrets


class Token:
    """An OAuth2 access/refresh token to access a service."""

    def __init__(self, access_token="", refresh_token="", *, provider: str, ensure_valid=True):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.provider = provider

        if ensure_valid:
            self._ensure_valid()

    @property
    def file(self):
        """The file containing the token."""
        return self.file_for_provider(self.provider)

    @staticmethod
    def file_for_provider(provider):
        return Path(__file__).parent / f"cache/.{provider}_token"

    def save(self):
        """Save the token to its file and the .env file."""
        if self.provider == "google":
            secrets[f"{self.provider.upper()}_REFRESH_TOKEN"] = self.refresh_token
            self.file.parent.mkdir(parents=True, exist_ok=True)
            self.file.write_text(self.access_token)

        if self.provider == "todoist":
            secrets[f"{self.provider.upper()}_TOKEN"] = self.access_token

    @classmethod
    def for_provider(cls, provider: str):
        """Get the token from its file. If it doesn't exist, raise an error."""
        file = Path(__file__).parent / f"cache/.{provider}_token"
        if file.exists():
            access_token = file.read_text()
        else:
            access_token = secrets.get(f"{provider.upper()}_TOKEN", "")

        if provider == "google":
            refresh_token = secrets.get(f"{provider.upper()}_REFRESH_TOKEN", "")
        else:
            refresh_token = ""

        if provider == "google" and not refresh_token or provider != "google" and not access_token:
            raise RuntimeError(f"Can't find {provider} token")

        return cls(access_token, refresh_token, provider=provider)

    @classmethod
    def delete(cls, provider: str):
        """Delete the token for a given provider."""
        secrets.pop(f"{provider.upper()}_TOKEN", "")
        secrets.pop(f"{provider.upper()}_REFRESH_TOKEN", "")
        cls.file_for_provider(provider).unlink(missing_ok=True)

    def _ensure_valid(self):
        """Ensure the token is valid by refreshing it if needed."""
        # If the Google token is expired, check if it is still valid
        if self.provider == "google":
            try:
                data = custom_requests.get(
                    "https://oauth2.googleapis.com/tokeninfo", {"access_token": self.access_token}
                ).json()
                # If the token is valid, stop here
                return
            except OSError:
                pass

        if self.provider == "todoist":
            # Check if the Todoist token is valid
            try:
                custom_requests.get("https://api.todoist.com/rest/v2/projects", token=self)
            except OSError as err:
                raise ValueError("The Todoist token is invalid") from err

        # Try to refresh the token
        token_refresh_url = {
            "google": "https://oauth2.googleapis.com/token",
        }.get(self.provider)
        params = {
            "google": {
                "client_id": secrets[f"{self.provider.upper()}_CLIENT_ID"],
                "client_secret": secrets[f"{self.provider.upper()}_CLIENT_SECRET"],
                "refresh_token": self.refresh_token,
                "grant_type": "refresh_token",
            }
        }.get(self.provider)
        # If there is nothing to do, stop here
        if not token_refresh_url or not params:
            return

        try:
            data = custom_requests.post(token_refresh_url, params).json()
        except OSError as err:
            if not hasattr(err, "response"):
                raise
            data: dict = err.response.json()  # type: ignore
            raise ValueError(
                f"Error while refreshing the token: {data.get('error', '')}: {data.get('error_description', '')}"
            ) from err

        # Save the new access token
        self.access_token = data.get("access_token", "")

        self.save()
