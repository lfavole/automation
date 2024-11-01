"""Utility functions to manage emails."""

import base64
import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
import hashlib
from dataclasses import dataclass
from functools import cached_property
from html.parser import HTMLParser
from io import StringIO
from typing import Self
from zoneinfo import ZoneInfo

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
    def from_bytes(cls, data: bytes) -> Self:
        """Create a `Message` from its bytes representation."""
        msg = email.message_from_bytes(data, policy=email.policy.default)
        headers = custom_requests.CaseInsensitiveDict(msg)

        date: dt.datetime = email.utils.parsedate_to_datetime(headers["Received"].split(";")[-1].strip()).astimezone(
            ZoneInfo("Europe/Paris")
        )
        sender = headers["From"]
        subject = headers["Subject"]
        body = get_body(msg)

        return cls(headers["Message-ID"], sender, subject, date, body)

    @cached_property
    def hashed_id(self):
        """A short representation of a message ID."""
        return base64.b64encode(hashlib.md5(self.id.strip("<>").encode()).digest())[:16].decode()


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
