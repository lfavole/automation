"""A Flask app that can be used to get Google or Todoist access/refresh tokens."""

# Install Flask if it's not already installed
import os
from importlib.util import find_spec

from todoist import to_json

if not find_spec("flask"):
    os.system("pip install flask")

if not find_spec("nacl"):
    os.system("pip install pynacl")

import datetime as dt
import hashlib
import imaplib
import re
import uuid
from base64 import b64encode
from dataclasses import dataclass
from html import escape
from pathlib import Path
from time import sleep
from urllib.parse import urlencode

from flask import Flask, Response, abort, redirect, render_template, request, session, url_for
from markupsafe import Markup
from nacl import encoding, public

import custom_requests
from get_secrets import secrets
from oauth_token import Token

app = Flask(__name__)


providers: dict[str, "Provider"] = {}


@dataclass
class Provider:
    id: str
    name: str
    image_basename: str
    patterns: tuple[str, str]
    token_classes: tuple[str, str, str, str]

    def __post_init__(self):
        providers[self.id] = self

    @property
    def image_url(self):
        hash = hashlib.md5(self.image_basename.encode()).hexdigest()[:2]
        return f"https://upload.wikimedia.org/wikipedia/commons/{hash[0]}/{hash}/{self.image_basename}"

    @property
    def image_tag(self):
        return Markup(f'<img src="{self.image_url}" alt="{self.name}">')


Provider(
    "google",
    "Google",
    "Google_2015_logo.svg",
    (r"\d{11}-[a-z0-9]{32}\.apps\.googleusercontent\.com", r"GOCSPX-[a-zA-Z0-9]{28}"),
    ("google-client-id", "google-client-secret", "google-access-token", "google-refresh-token"),
)
Provider(
    "todoist",
    "Todoist",
    "Todoist_logo.png",
    (r"[0-9a-f]{32}", r"[0-9a-f]{32}"),
    ("todoist-token", "todoist-token", "todoist-token", ""),
)
Provider("gmx", "GMX", "GMX_2018_logo.svg", ("", ""), ("", "", "", ""))


app.before_request(secrets.reload)


@app.route("/")
def index():
    """Home page."""
    providers_ok = {}

    for provider in providers.values():
        if provider.id == "gmx":
            ok = secrets.get(f"{provider.id.upper()}_USER") and secrets.get(f"{provider.id.upper()}_PASSWORD")
            if ok:
                conn = imaplib.IMAP4_SSL("imap.gmx.com")
                try:
                    conn.login(
                        secrets.get(f"{provider.id.upper()}_USER", ""),
                        secrets.get(f"{provider.id.upper()}_PASSWORD", ""),
                    )
                except imaplib.IMAP4.error:
                    ok = False
                finally:
                    conn.logout()
        else:
            ok = secrets.get(f"{provider.id.upper()}_CLIENT_ID") and secrets.get(f"{provider.id.upper()}_CLIENT_SECRET")
            if ok:
                try:
                    Token.for_provider(provider.id)
                except (RuntimeError, ValueError):
                    ok = False
        providers_ok[provider.id] = ok

    all_ok = all(providers_ok.values())

    return render_template("index.html", providers=providers.values(), providers_ok=providers_ok, all_ok=all_ok)


@app.route("/favicon.ico")
def favicon():
    """Favicon page that returns a 404 error."""
    abort(404)


@app.route("/gmx", methods=["GET", "POST"])
def gmx():
    if "delete" in request.form:
        secrets.pop("GMX_USER", "")
        secrets.pop("GMX_PASSWORD", "")
        return redirect("/gmx")

    if request.method == "POST":
        secrets["GMX_USER"] = request.form["email"]
        secrets["GMX_PASSWORD"] = request.form["password"]
        return redirect("/gmx")

    gmx_user = secrets.get("GMX_USER", "")
    gmx_password = secrets.get("GMX_PASSWORD", "")
    context = {
        "gmx": providers["gmx"],
        "GMX_USER": gmx_user,
        "GMX_PASSWORD": gmx_password,
    }

    if not gmx_user or not gmx_password or request.args.get("form"):
        return render_template("gmx_credentials_form.html", **context)

    conn = imaplib.IMAP4_SSL("imap.gmx.com")
    try:
        conn.login(gmx_user, gmx_password)
    except imaplib.IMAP4.error as err:
        error_message = err.args[0]
        if isinstance(error_message, bytes):
            error_message = error_message.decode(errors="replace")
        return provider_error(providers["gmx"], error_message, delete=True)
    finally:
        conn.logout()

    return render_template("gmx_credentials.html", **context)


def provider_interstitial(provider: Provider):
    return render_template("provider_interstitial.html", provider=providers[provider.id])


def provider_error(provider: Provider, error: str, delete=False):
    return Response(render_template("provider_error.html", provider=provider, error=error, delete=delete), status=400)


@app.route("/<provider_name>", methods=["GET", "POST"])
def provider_oauth(provider_name):
    """OAuth page for a provider."""
    if provider_name not in providers:
        abort(404)
    provider = providers[provider_name]

    if "delete" in request.form:
        Token.delete(provider.id)

    if request.method == "POST" and ("client_id" in request.form or "client_secret" in request.form):
        secrets[f"{provider.id.upper()}_CLIENT_ID"] = request.form["client_id"]
        secrets[f"{provider.id.upper()}_CLIENT_SECRET"] = request.form["client_secret"]
        return redirect(f"/{provider.id}")

    # Get the settings
    client_id = secrets.get(f"{provider.id.upper()}_CLIENT_ID", "")
    client_secret = secrets.get(f"{provider.id.upper()}_CLIENT_SECRET", "")
    redirect_uri = "http://127.0.0.1:5000/" + provider.id

    secrets_missing = not client_id or not client_secret
    if secrets_missing or request.args.get("edit"):
        return render_template(
            "provider_credentials_form.html",
            provider=provider,
            secrets_missing=secrets_missing,
            client_id=client_id,
            client_secret=client_secret,
        )

    # If there is an error from the provider, show it
    if "error" in request.args:
        return provider_error(provider, escape(request.args["error"]))

    # If we have the access code, get an access token and a refresh token
    if "code" in request.args:
        access_token_url = {
            "google": "https://oauth2.googleapis.com/token",
            "todoist": "https://todoist.com/oauth/access_token",
        }[provider.id]

        # Check the state
        if f"{provider.id}_state" not in session:
            return provider_error(
                provider,
                Markup(
                    """\
The state doesn't exist.
<br>
This means that is hasn't been created by the app: you might have accessed the URL directly instead of using the app.
"""
                ),
            )
        state = session[f"{provider.id}_state"]
        if state != request.args["state"]:
            return provider_error(
                provider,
                Markup(
                    f"""\
The state provided by {provider.name} doesn't match the state from the app.
<ul>
    <li>You might have reused another Google login tab.</li>
    <li>You might have deleted the <code>cache/.secret_key</code> file.</li>
</ul>
"""
                ),
            )

        # Get the access token
        code = request.args["code"]
        get_access_token_data = {
            "google": {
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
        }.get(provider.id, {})

        req = custom_requests.post(
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
            provider=provider.id,
            ensure_valid=False,
        )
        token.save()

        if provider.id == "google" and not data.get("refresh_token", ""):
            return redirect(url_for("refresh_token_error", provider=provider.id))

        # Redirect to the provider page to hide the URL query string
        return redirect("/" + provider.id)

    # If we have already saved a token, show it
    try:
        token = Token.for_provider(provider.id)
    except RuntimeError:
        pass
    except ValueError as err:
        return provider_error(provider, str(err), delete=True)
    else:
        return render_template("provider_credentials.html", provider=provider, token=token)

    if request.method != "POST":
        return provider_interstitial(provider)

    # Otherwise, redirect to the service
    url = {
        "google": "https://accounts.google.com/o/oauth2/v2/auth",
        "todoist": "https://todoist.com/oauth/authorize",
    }[provider.id]

    # Create the state
    if f"{provider.id}_state" not in session:
        session[f"{provider.id}_state"] = str(uuid.uuid4())
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
        },
    }[provider.id]
    params["state"] = session[f"{provider.id}_state"]

    return app.redirect(url + "?" + urlencode(params))


@app.route("/<provider>/refresh-token-error")
def refresh_token_error(provider):
    try:
        Token.for_provider(provider)
    except RuntimeError:
        # If there is no refresh token but an access token...
        if Token.file_for_provider(provider).exists():
            # ...show the error page
            return provider_error(
                providers[provider],
                Markup(
                    """\
Could not get the refresh token.
<br>
Please go to the
<a href="https://myaccount.google.com/connections" target="_blank">Third-party apps & services</a>
page, find your Google app and revoke the access.
"""
                ),
            )

    return redirect(f"/{provider}")


@app.route("/secrets", methods=["GET", "POST"])
def add_secrets():
    if request.method == "POST":
        # https://docs.github.com/fr/rest/guides/encrypting-secrets-for-the-rest-api#example-encrypting-a-secret-using-python
        def encrypt(public_key: str, secret_value: str) -> str:
            """Encrypt a Unicode string using the public key."""
            pkey = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())  # type: ignore
            sealed_box = public.SealedBox(pkey)
            encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
            return b64encode(encrypted).decode(errors="replace")

        token = request.form["token"]
        session["GITHUB_PAT"] = token
        repo_url_part = (re.search(r"^.*/(.*?/.*?)$", request.form["repo_url"].rstrip("/")) or ["", ""])[1]
        session["REPO_URL_PART"] = repo_url_part

        data = custom_requests.get(
            f"https://api.github.com/repos/{repo_url_part}/actions/secrets/public-key", token=token
        ).json()

        for key, value in secrets.items():
            encrypted_value = encrypt(data["key"], value)
            custom_requests.put(
                f"https://api.github.com/repos/{repo_url_part}/actions/secrets/{key}",
                json={"encrypted_value": encrypted_value, "key_id": data["key_id"]},
                token=token,
            )

        custom_requests.post(
            f"https://api.github.com/repos/{repo_url_part}/actions/workflows/automation.yml/dispatches",
            json={"ref": "main"},
            token=token,
        )

        for _ in range(3):
            sleep(5)
            data = custom_requests.get(
                f"https://api.github.com/repos/{repo_url_part}/actions/runs?event=workflow_dispatch&per_page=1",
                token=token,
            ).json()
            try:
                date = dt.datetime.fromisoformat(data["workflow_runs"][0]["created_at"])
                if date + dt.timedelta(seconds=30) >= dt.datetime.now(dt.UTC):
                    session["WORKFLOW_RUN_ID"] = data["workflow_runs"][0]["id"]
                    break
            except (IndexError, KeyError):
                pass
        else:
            raise ValueError("Could not get the workflow URL")

        return redirect("/end")

    return render_template("add_secrets_form.html")


@app.route("/end")
def end():
    return render_template("end.html")


@app.route("/status")
def status():
    repo_url_part = session.get("REPO_URL_PART", "")
    token = session.get("GITHUB_PAT", "")
    workflow_run_id = session.get("WORKFLOW_RUN_ID", "")
    if not token or not workflow_run_id:
        abort(404)
    data = custom_requests.get(
        f"https://api.github.com/repos/{repo_url_part}/actions/runs/{workflow_run_id}/jobs", token=token
    ).json()["jobs"][0]
    return Response(to_json({"status": data["status"], "conclusion": data["conclusion"], "job_url": data["html_url"]}))


if __name__ == "__main__":
    secret_key_path = Path(__file__).parent / "cache/.secret_key"
    secret_key_path.parent.mkdir(parents=True, exist_ok=True)
    if secret_key_path.exists():
        app.secret_key = secret_key_path.read_text("utf-8")
    else:
        app.secret_key = str(uuid.uuid4())
        secret_key_path.write_text(app.secret_key, "utf-8")
    app.run(debug=True, load_dotenv=False)
