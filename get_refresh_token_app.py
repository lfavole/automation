import uuid
from urllib.parse import unquote, urlencode

from flask import Flask, Response, abort, redirect, request, session

import custom_requests
from get_secrets import get_secret
from oauth_token import Token

app = Flask(__name__)


@app.route("/")
def index():
    """
    Home page.
    """
    return """\
<ul>
    <li><a href="/google">Google</a></li>
    <li><a href="/todoist">Todoist</a></li>
</ul>
"""


@app.route("/favicon.ico")
def favicon():
    """
    Favicon page that responds with a 404 error.
    """
    abort(404)


@app.route("/<provider>")
def provider_oauth(provider):
    """
    OAuth page for a provider.
    """
    # get the settings
    client_id = get_secret(provider.upper() + "_CLIENT_ID")
    client_secret = get_secret(provider.upper() + "_CLIENT_SECRET")

    redirect_uri = "http://127.0.0.1:5000/" + provider

    params = {
        unquote(key): unquote(value)
        for key, _, value in (part.partition(b"=") for part in request.query_string.split(b"&"))
    }

    # if there is an error, show it
    if "error" in params:
        return Response(f"Error: {params['error']}", content_type="text/plain")

    # if we have the access code, get an access token and a refresh token
    if "code" in params:
        access_token_method = {}.get(provider, "POST")
        access_token_url = {
            "google": "https://oauth2.googleapis.com/token",
            "todoist": "https://todoist.com/oauth/access_token",
        }[provider]

        if provider == "todoist":
            state = session["TODOIST_STATE"]
            if state != params["state"]:
                return "State mismatch"

        code = params["code"]
        get_access_token_data = {
            "google": {
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        }.get(provider, {})

        req = custom_requests.request(
            access_token_method,
            access_token_url,
            data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                **get_access_token_data,
            },
        )
        data = req.json()
        token = Token(
            data["access_token"], data.get("refresh_token", ""), data.get("expires_in", ""), provider=provider
        )
        token.save()
        session[provider] = True
        return redirect("/" + provider)

    # if we have saved a token, show it
    try:
        token = Token.from_file(provider)
    except RuntimeError:
        pass
    else:
        return Response(
            f"""\
Access token: {token.access_token}

Refresh token: {token.refresh_token}

Expires at: {token.expires_at}
""",
            content_type="text/plain",
        )

    # otherwise, redirect to the service
    url = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "todoist": "https://todoist.com/oauth/authorize",
    }[provider]

    if "TODOIST_STATE" not in session:
        session["TODOIST_STATE"] = str(uuid.uuid4())
        session.modified = True

    params = {
        "google": {
            "scope": "https://www.googleapis.com/auth/tasks https://www.googleapis.com/auth/gmail.readonly",
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

    return redirect(url + "?" + urlencode(params))


if __name__ == "__main__":
    app.secret_key = str(uuid.uuid4())
    app.run(debug=True)
