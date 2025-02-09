"""Functions to get emails from Gmail."""

import base64
from pathlib import Path

import custom_requests
from email_utils import Message
from oauth_token import Token


def get_content(message_id: str) -> bytes:
    """Get the content of a message from the ID given by the Gmail API."""
    file = Path(__file__).parent / f"cache/message_{message_id}"
    if file.exists():
        return file.read_bytes()
    data = custom_requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=raw",
        token=Token.for_provider("google"),
    ).json()
    ret = base64.urlsafe_b64decode(data["raw"])
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_bytes(ret)
    return ret


def get_gmail_emails():
    """Return all the emails in the Gmail inbox."""
    message_ids = (
        message["id"]
        for message in custom_requests.get_with_pages(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            {
                "includeSpamTrash": "false",
                "labelIds": "INBOX",
            },
            token=Token.for_provider("google"),
        )
    )

    for message_id in message_ids:
        yield Message.from_bytes(get_content(message_id), "gmail")
