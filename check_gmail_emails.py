import base64
import json
from pathlib import Path

import custom_requests
from handle_messages import handle_deleted_message, handle_new_message
from oauth_token import Token

token = Token.from_file("google")
token.ensure_valid()

MESSAGES_FILE = Path(__file__).parent / "gmail_messages.json"
if not MESSAGES_FILE.exists():
    MESSAGES_FILE.touch()
    old_messages = []
else:
    old_messages = json.loads(MESSAGES_FILE.read_text())

messages = [
    message["id"]
    for message in custom_requests.get_with_pages(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages",
        {
            "includeSpamTrash": "false",
            "labelIds": "INBOX",
        },
        token=token,
    )
]

new = []
deleted = []

for message in messages:
    if message not in old_messages:
        new.append(message)

for message in old_messages:
    if message not in messages:
        deleted.append(message)


print("New messages:", *new)


def get_content(message):
    data = custom_requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message}?format=raw",
        token=token,
    ).json()
    return base64.urlsafe_b64decode(data["raw"])


for message in new:
    handle_new_message(message, get_content)
    old_messages.append(message)

print("Deleted messages:", *deleted)

for message in deleted:
    handle_deleted_message(message, get_content)
    old_messages.remove(message)

MESSAGES_FILE.write_text(json.dumps(messages))

assert old_messages == messages
