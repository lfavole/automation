"""Functions to get emails from Gmail."""

import base64

import custom_requests
from email_utils import Message
from oauth_token import Token

token = Token.from_file("google")


def get_content(message_id: str) -> bytes:
    """Get the content of a message from the ID given by the Gmail API."""
    data = custom_requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=raw",
        token=token,
    ).json()
    return base64.urlsafe_b64decode(data["raw"])


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
            token=token,
        )
    )

    for message_id in message_ids:
        yield Message.from_bytes(get_content(message_id))
