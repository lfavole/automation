import datetime as dt
import email.header
import email.message
import email.policy
import email.utils
from typing import Callable

import custom_requests
from email_utils import get_body
from tasks import add_task


def handle_new_message(message_id: str, content_callback: Callable[[], bytes]):
    """
    Handle a new message.
    """
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


def handle_deleted_message(message_id: str):
    """
    Handle a deleted message.
    """
