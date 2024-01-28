from urllib.parse import unquote, urlencode

import custom_requests
from flask import Flask, abort, redirect, request, session
from get_secrets import get_secret
from oauth_token import Token

app = Flask(__name__)


@app.route("/")
def index():
    return """\
<ul>
    <li><a href="/google">Google</a></li>
    <li><a href="/todoist">Todoist</a></li>
</ul>
"""


@app.route("/favicon.ico")
def favicon():
    abort(404)


@app.route("/<provider>")
def provider_oauth(provider):
    if provider in session:
        return f"Refresh token is: {session[provider]}"

    client_id = get_secret(provider.upper() + "_CLIENT_ID")
    client_secret = get_secret(provider.upper() + "_CLIENT_SECRET")

    redirect_uri = "http://127.0.0.1:5000/" + provider

    params = {
        unquote(key): unquote(value)
        for key, _, value in (part.partition(b"=") for part in request.query_string.split(b"&"))
    }

    if "error" in params:
        return f"Error: {params['error']}"

    if "code" in params:
        access_token_method = {
            "google": "POST",
            "todoist": "POST",
        }[provider]
        access_token_url = {
            "google": "https://oauth2.googleapis.com/token",
            "todoist": "https://todoist.com/oauth/access_token",
        }[provider]

        if provider == "todoist":
            state = session["state"]
            if state != params["state"]:
                return "State mismatch"

        code = params["code"]
        get_access_token_data = {
            "google": {
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            "todoist": {},
        }

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
        token = Token(data["access_token"], data["refresh_token"], data["expires_in"])
        token.ensure_valid()
        token.save()
        session[provider] = token.refresh_token
        return redirect("/" + provider)

    url = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "todoist": "https://todoist.com/oauth/authorize",
    }[provider]
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
            "scope": "task:add data:delete",
            "state": session.setdefault("TODOIST_STATE", str(uuid.uuid4())),
        },
    }[provider]

    return redirect(url + "?" + urlencode(params))


if __name__ == "__main__":
    import uuid
    app.secret_key = str(uuid.uuid4())
    app.run(debug=True)
