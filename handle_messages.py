import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
import json
from html.parser import HTMLParser
from io import StringIO
from pathlib import Path

import custom_requests
from tasks import add_task


def defer(ret):
    return lambda: ret


def handle_messages_list(provider, messages):
    messages_file = Path(__file__).parent / f"{provider}_messages.json"
    if not messages_file.exists():
        old_messages_ids = []
    else:
        old_messages_ids = json.loads(messages_file.read_text())

    messages_dict = {}

    for message_id, message in messages:
        if message_id is None:
            message_text = message()
            msg = email.message_from_bytes(message_text, policy=email.policy.default)
            headers = custom_requests.CaseInsensitiveDict(msg)
            message_id = headers["Message-ID"]
            message = defer(message_text)

        messages_dict[message_id] = message

    new_ids = []
    deleted_ids = []

    for message_id in messages_dict:
        if message_id not in old_messages_ids:
            new_ids.append(message_id)

    for message_id in old_messages_ids:
        if message_id not in messages_dict:
            deleted_ids.append(message_id)

    print("New messages:", *new_ids)
    for message_id in new_ids:
        handle_new_message(message_id, messages_dict[message_id])
        old_messages_ids.append(message_id)

    print("Deleted messages:", *deleted_ids)
    for message_id in deleted_ids:
        handle_deleted_message(message_id, messages_dict[message_id])
        old_messages_ids.remove(message_id)

    messages_ids = list(messages_dict.keys())

    messages_file.write_text(json.dumps(messages_ids))

    assert old_messages_ids == messages_ids


class TagsStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = StringIO()

    def handle_data(self, data):
        self.text.write(data)

    def get_data(self):
        return self.text.getvalue()


def get_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload()

    for part in msg.walk():
        if part.get_content_type() == "text/html":
            parser = TagsStripper()
            parser.feed(part.get_payload())
            return parser.get_data()

    return ""


def handle_new_message(message_id, content_callback):
    msg = email.message_from_bytes(content_callback(), policy=email.policy.default)
    headers = custom_requests.CaseInsensitiveDict(msg)

    date: dt.datetime = email.utils.parsedate_to_datetime(headers["Received"].split(";")[-1].strip()).astimezone()
    due_date = date + dt.timedelta(days=7)
    sender = headers["From"]
    subject = headers["Subject"]

    notes_end = f"\n\nID : {message_id}"

    body = get_body(msg)
    add_task(
        f"Répondre à {sender}",
        f"{subject}\n\n{body}"[: 8192 - len(notes_end)] + notes_end,
        due_date,
    )
    print("Task created")


def handle_deleted_message(message_id, content_callback):
    pass
