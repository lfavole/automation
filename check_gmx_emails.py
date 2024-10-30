import imaplib
from typing import Iterable

from email_utils import Message, handle_message_list
from get_secrets import get_secret


def get_messages() -> Iterable[Message]:
    """Yield all messages on GMX."""
    conn = imaplib.IMAP4_SSL("imap.gmx.com")
    try:
        conn.login(get_secret("GMX_USER"), get_secret("GMX_PASSWORD"))
        conn.select(readonly=True)
        _, data = conn.search(None, "(ALL)")
        for num in data[0].split():
            typ, data = conn.fetch(num, "(RFC822)")
            if typ != "OK":
                raise RuntimeError(f"Error getting message {num}")
            yield Message.from_bytes(data[0][1])  # type: ignore
    finally:
        conn.close()
        conn.logout()


def check_gmx_emails():
    handle_message_list("gmx", ((message.id, message) for message in get_messages()))
