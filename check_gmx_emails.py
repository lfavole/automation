"""Functions to get emails from GMX."""

import imaplib
from typing import Iterable

from email_utils import Message
from get_secrets import secrets


def get_gmx_emails() -> Iterable[Message]:
    """Yield all messages on GMX."""
    conn = imaplib.IMAP4_SSL("imap.gmx.com")
    try:
        conn.login(secrets["GMX_USER"], secrets["GMX_PASSWORD"])
        conn.select(readonly=True)
        _, data = conn.search(None, "(ALL)")
        for num in data[0].split():
            typ, data = conn.fetch(num, "(RFC822)")
            if typ != "OK":
                raise RuntimeError(f"Error getting message {num}")
            yield Message.from_bytes(data[0][1], "gmx")  # type: ignore
    finally:
        conn.close()
        conn.logout()
