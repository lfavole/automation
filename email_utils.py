import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
import json
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Iterable, Self

import custom_requests


@dataclass
class Message:
    """An email message."""
    id: str
    sender: str
    subject: str
    date: dt.datetime
    body: str

    @classmethod
    def from_bytes(cls, data: bytes, message_id: str | None = None) -> Self:
        """Create a `Message` from its bytes representation."""
        msg = email.message_from_bytes(data, policy=email.policy.default)
        headers = custom_requests.CaseInsensitiveDict(msg)

        date: dt.datetime = email.utils.parsedate_to_datetime(headers["Received"].split(";")[-1].strip()).astimezone()
        sender = headers["From"]
        subject = headers["Subject"]
        body = get_body(msg)

        return cls(message_id or headers["Message-ID"], sender, subject, date, body)


def handle_message_list(provider: str, messages: Iterable[tuple[str, Message]]):
    """
    Compare a message list with the message IDs stored on disk and call the
    `handle_new_message` and `handle_deleted_message` functions.
    """
    # avoid circular imports
    from handle_messages import handle_deleted_message, handle_new_message

    # open the list
    messages_file = Path(__file__).parent / f"{provider}_messages.json"
    if not messages_file.exists():
        old_message_ids = []
    else:
        old_message_ids: list[str] = json.loads(messages_file.read_text())

    # store all the messages in a dict with their ID
    messages_dict: dict[str, Message] = {}

    # new messages
    for message_id, message in messages:
        messages_dict[message_id] = message
        if message_id not in old_message_ids:
            print(f"New message: {message_id}")
            handle_new_message(message)
            old_message_ids.append(message_id)

    # deleted messages
    for message_id in old_message_ids:
        if message_id not in messages_dict:
            print(f"Deleted message: {message_id}")
            handle_deleted_message(message_id)
            old_message_ids.remove(message_id)

    # save the message IDs
    message_ids = list(messages_dict.keys())
    messages_file.write_text(json.dumps(message_ids))

    assert old_message_ids == message_ids


class TagsStripper(HTMLParser):
    """A HTML parser that strips tags."""

    def __init__(self):
        super().__init__()
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        """Return the text in the parsed HTML."""
        return self.text.getvalue()


def get_body(msg: email.message.Message) -> str:
    """Return the body of a `Message` as plain text."""
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True)

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            parser = TagsStripper()
            parser.feed(part.get_payload())
            return parser.get_data()

    return ""
