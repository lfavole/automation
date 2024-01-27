import datetime as dt
import json
from pathlib import Path
import custom_requests
from oauth_token import Token

token = Token.from_file()
token.ensure_valid()

MESSAGES_FILE = Path(__file__).parent / "messages.json"
if not MESSAGES_FILE.exists():
    MESSAGES_FILE.touch()
    old_messages = []
else:
    old_messages = json.loads(MESSAGES_FILE.read_text())

messages = []
next_page_token = None
while True:
    data = custom_requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        {
            "includeSpamTrash": "false",
            "labelIds": "INBOX",
            **({"pageToken": next_page_token} if next_page_token else {}),
        },
        token=token,
    ).json()
    messages.extend(message["id"] for message in data["messages"])
    next_page_token = data.get("nextPageToken")
    if next_page_token is None:
        break

new = []
deleted = []

for message in messages:
    if message not in old_messages:
        new.append(message)

for message in old_messages:
    if message not in messages:
        deleted.append(message)


print("New messages:", *new)

for message in new:
    data = custom_requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages/" + message,
        token=token,
    ).json()
    date = dt.datetime.fromtimestamp(data.get("internalDate", 0))
    due_date = date + dt.timedelta(days=7)
    headers = custom_requests.CaseInsensitiveDict(
        {header["key"]: header["value"] for header in data["payload"]["headers"]}
    )
    sender = headers["From"]
    subject = headers["Subject"]
    old_messages.append(message)

print("Deleted messages:", *deleted)

for message in deleted:
    old_messages.remove(message)

MESSAGES_FILE.write_text(json.dumps(messages))

assert old_messages == messages
