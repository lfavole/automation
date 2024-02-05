import email.header
import email.message
import email.policy
import email.utils
import json
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
from typing import Callable, TypeVar

import custom_requests
from handle_messages import handle_deleted_message, handle_new_message

T = TypeVar("T")


def defer(ret: T) -> Callable[[], T]:
    """
    Returns a deferred callable that returns a specific value.
    """
    return lambda: ret


def handle_message_list(provider: str, messages: list[tuple[str | None, Callable[[], bytes]]]):
    """
    Compare a message list with the message IDs stored on disk and call the
    `handle_new_message` and `handle_deleted_message` functions.
    """
    # open the list
    messages_file = Path(__file__).parent / f"{provider}_messages.json"
    if not messages_file.exists():
        old_message_ids = []
    else:
        old_message_ids: list[str] = json.loads(messages_file.read_text())

    # store all the messages in a dict with their ID
    messages_dict: dict[str, Callable[[], bytes]] = {}

    for message_id, message in messages:
        if message_id is None:
            message_text = message()
            msg = email.message_from_bytes(message_text, policy=email.policy.default)
            headers = custom_requests.CaseInsensitiveDict(msg)
            message_id = headers["Message-ID"]
            message = defer(message_text)

        messages_dict[message_id] = message

    # new messages
    for message_id, message in messages_dict.items():
        if message_id not in old_message_ids:
            print(f"New message: {message_id}")
            handle_new_message(message_id, message)
            old_message_ids.append(message_id)

    # deleted messages
    for message_id in old_message_ids:
        if message_id not in messages_dict:
            print(f"Deleted message: {message_id}")
            handle_deleted_message(message_id, messages_dict[message_id])  # FIXME deleted messages don't exist
            old_message_ids.remove(message_id)

    # save the message IDs
    message_ids = list(messages_dict.keys())
    messages_file.write_text(json.dumps(message_ids))

    assert old_message_ids == message_ids


class TagsStripper(HTMLParser):
    """
    A HTML parser that strips tags.
    """
    def __init__(self):
        super().__init__()
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        """
        Returns the text in the parsed HTML.
        """
        return self.text.getvalue()


def get_body(msg: email.message.Message) -> str:
    """
    Returns the message body as plain text.
    """
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload()

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            parser = TagsStripper()
            parser.feed(part.get_payload())
            return parser.get_data()

    return ""
