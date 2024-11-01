"""
A Flask app that can be used to get Google or Todoist access/refresh tokens.

To use this app, you must:
1. Install Flask (`pip install flask`).
2. Register a Google app and a Todoist app and pass the
   `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `TODOIST_CLIENT_ID` and `TODOIST_CLIENT_SECRET`
   environment variables or create a `.env` file with these variables.
"""

import uuid
from html import escape
from urllib.parse import urlencode

from flask import Flask, Response, abort, redirect, request, session

import custom_requests
from get_secrets import secrets
from oauth_token import Token

app = Flask(__name__)


@app.route("/")
def index():
    """Home page."""
    return """\
<ul>
    <li><a href="/google">Google</a></li>
    <li><a href="/todoist">Todoist</a></li>
</ul>
"""


@app.route("/favicon.ico")
def favicon():
    """Favicon page that returns a 404 error."""
    abort(404)


@app.route("/<provider>")
def provider_oauth(provider):
    """OAuth page for a provider."""
    # Get the settings
    client_id = secrets[f"{provider.upper()}_CLIENT_ID"]
    client_secret = secrets[f"{provider.upper()}_CLIENT_SECRET"]
    redirect_uri = "http://127.0.0.1:5000/" + provider

    # If there is an error from the provider, show it
    if "error" in request.args:
        return Response(f"Error: {request.args['error']}", content_type="text/plain")

    # If we have the access code, get an access token and a refresh token
    if "code" in request.args:
        access_token_url = {
            "google": "https://oauth2.googleapis.com/token",
            "todoist": "https://todoist.com/oauth/access_token",
        }[provider]

        # Check the Todoist state
        if provider == "todoist":
            state = session["TODOIST_STATE"]
            if state != request.args["state"]:
                return "State mismatch"

        # Get the access token
        code = request.args["code"]
        get_access_token_data = {
            "google": {
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        }.get(provider, {})

        req = custom_requests.get(
            access_token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                **get_access_token_data,
            },
        )
        data = req.json()
        # Create the token object and save it
        token = Token(
            data["access_token"],
            data.get("refresh_token", ""),
            data.get("expires_in", ""),
            provider=provider,
        )
        token.save()
        # Redirect to the provider page to hide the URL query string
        return redirect("/" + provider)

    # If we have already saved a token, show it
    try:
        token = Token.from_file(provider)
    except RuntimeError:
        pass
    else:
        return f"""\
<a href="/">← Back</a>
<ul>
    <li>Access token: <input disabled value="{escape(token.access_token)}"></li>
    <li>Refresh token: <input disabled value="{escape(token.refresh_token)}"></li>
    <li>Expires at: {escape(str(token.expires_at))}</li>
</li>
"""

    # Otherwise, redirect to the service
    url = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "todoist": "https://todoist.com/oauth/authorize",
    }[provider]

    # Create the Todoist state
    if "TODOIST_STATE" not in session:
        session["TODOIST_STATE"] = str(uuid.uuid4())
        session.modified = True

    params = {
        "google": {
            "scope": "https://www.googleapis.com/auth/gmail.readonly",
            "access_type": "offline",
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "include_granted_scopes": "true",
        },
        "todoist": {
            "client_id": client_id,
            "scope": "data:read_write",
            "state": session["TODOIST_STATE"],
        },
    }[provider]

    return app.redirect(url + "?" + urlencode(params))


if __name__ == "__main__":
    app.secret_key = str(uuid.uuid4())
    app.run(debug=True)
