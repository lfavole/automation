import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
import hashlib
import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Iterable, Self

import custom_requests
from tasks import Task


def hash_message_id(id: str):
    return hashlib.md5(id.strip("<>").encode()).hexdigest()[:8]


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


tasks = None


def handle_message_list(provider: str, messages: Iterable[tuple[str, Message]]):
    """
    Compare a message list with the message IDs stored on disk and call the
    `handle_new_message` and `handle_deleted_message` functions.
    """
    global tasks

    # avoid circular imports
    from handle_messages import handle_deleted_message, handle_new_message

    # open the list
    messages_file = Path(__file__).parent / f"{provider}_messages.json"
    if not messages_file.exists():
        old_message_ids = []
    else:
        old_message_ids: list[str] = json.loads(messages_file.read_text())

    if tasks is None:
        tasks = Task.all()

    not_new_messages: list[str] = []

    # new messages
    for id, message in messages:
        new = True
        for task in tasks:
            if hash_message_id(id) in task.description:
                new = False
                break
        if new:
            print(f"New message: {id}")
            handle_new_message(message)
            old_message_ids.append(id)
        else:
            not_new_messages.append(id)

    # deleted messages
    for task in tasks:
        id = re.match(r"\n\nID : (.*?)$", task.description)
        if id in not_new_messages:
            print(f"Deleted message: {id}")
            handle_deleted_message(id)
            old_message_ids.remove(id)


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
            return part.get_payload(decode=True).decode()

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            parser = TagsStripper()
            parser.feed(part.get_payload(decode=True).decode())
            return parser.get_data()

    return ""
