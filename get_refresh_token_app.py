import uuid
from urllib.parse import unquote, urlencode

import custom_requests
from flask import Flask, Response, abort, redirect, request, session
from get_secrets import get_secret
from oauth_token import Token

app = Flask(__name__)


@app.route("/")
def index():
    return """\
<ul>
    <li><a href="/google">Google</a></li>
    <li><a href="/ticktick">TickTick</a></li>
    <li><a href="/todoist">Todoist</a></li>
</ul>
"""


@app.route("/favicon.ico")
def favicon():
    abort(404)


@app.route("/<provider>")
def provider_oauth(provider):
    client_id = get_secret(provider.upper() + "_CLIENT_ID")
    client_secret = get_secret(provider.upper() + "_CLIENT_SECRET")

    redirect_uri = "http://127.0.0.1:5000/" + provider

    params = {
        unquote(key): unquote(value)
        for key, _, value in (part.partition(b"=") for part in request.query_string.split(b"&"))
    }

    if "error" in params:
        return Response(f"Error: {params['error']}", content_type="text/plain")

    if "code" in params:
        access_token_method = {}.get(provider, "POST")
        access_token_url = {
            "google": "https://oauth2.googleapis.com/token",
            "todoist": "https://todoist.com/oauth/access_token",
            "ticktick": "https://ticktick.com/oauth/token",
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
            "ticktick": {
                "grant_type": "authorization_code",
                "scope": "tasks:write tasks:read",
                "redirect_uri": redirect_uri,
            }
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
        token = Token(data["access_token"], data.get("refresh_token", ""), data.get("expires_in", ""), provider)
        token.ensure_valid()
        token.save()
        session[provider] = True
        return redirect("/" + provider)

    token = Token.from_file(provider)
    if token:
        return Response(f"""\
Access token: {token.access_token}

Refresh token: {token.refresh_token}

Expires at: {token.expires_at}
""", content_type="text/plain")

    url = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "todoist": "https://todoist.com/oauth/authorize",
        "ticktick": "https://ticktick.com/oauth/authorize",
    }[provider]

    if "TODOIST_STATE" not in session:
        session["TODOIST_STATE"] = str(uuid.uuid4())
        session.modified = True
    if "TICKTICK_STATE" not in session:
        session["TICKTICK_STATE"] = str(uuid.uuid4())
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
            "scope": "task:add,data:delete",
            "state": session["TODOIST_STATE"],
        },
        "ticktick": {
            "client_id": client_id,
            "scope": "tasks:write tasks:read",
            "state": session["TICKTICK_STATE"],
            "redirect_uri": redirect_uri,
            "response_type": "code",
        },
    }[provider]

    return redirect(url + "?" + urlencode(params))


if __name__ == "__main__":
    app.secret_key = str(uuid.uuid4())
    app.run(debug=True)
