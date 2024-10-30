import base64

import custom_requests
from email_utils import Message, handle_message_list
from oauth_token import Token

token = Token.from_file("google")


def get_content(message_id: str) -> bytes:
    """
    Gets the content of a message with ID via the Gmail API.
    """
    data = custom_requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message_id}?format=raw",
        token=token,
    ).json()
    return base64.urlsafe_b64decode(data["raw"])


def check_gmail_emails():
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

    handle_message_list(
        "gmail", ((message_id, Message.from_bytes(get_content(message_id), message_id)) for message_id in message_ids)
    )
