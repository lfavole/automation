import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
from html.parser import HTMLParser
from io import StringIO

import custom_requests
from tasks import add_task


def get_content(content_callback):
    if isinstance(content_callback, str):
        return content_callback
    return content_callback()


class TagsStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = StringIO()

    def handle_data(self, d):
        self.text.write(d)

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
    msg = email.message_from_bytes(get_content(content_callback), policy=email.policy.default)
    headers = custom_requests.CaseInsensitiveDict(msg)
    message_id = message_id or headers["Message-ID"]

    date: dt.datetime = email.utils.parsedate_to_datetime(headers["Received"].split(";")[-1].strip()).astimezone()
    due_date = date + dt.timedelta(days=7)
    sender = headers["From"]
    subject = headers["Subject"]

    notes_end = f"\n\nID : {message_id}"

    body = get_body(msg)
    add_task(
        f"Répondre à {sender}",
        f"{subject}\n\n{body}"[:8192 - len(notes_end)] + notes_end,
        due_date,
    )
    print("Task created")


def handle_deleted_message(message_id, content_callback):
    pass
