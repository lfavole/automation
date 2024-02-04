import imaplib

from get_secrets import get_secret
from handle_messages import handle_new_message

messages = []

conn = imaplib.IMAP4_SSL("imap.gmx.com")
try:
    conn.login(get_secret("GMX_USER"), get_secret("GMX_PASSWORD"))
    conn.select(readonly=True)
    typ, data = conn.search(None, "(ALL)")
    for num in data[0].split():
        typ, data = conn.fetch(num, "(RFC822)")
        if typ != "OK":
            raise RuntimeError(f"Error getting message {num}")
        messages.append(data[0][1])  # type: ignore
finally:
    conn.close()
    conn.logout()


for msg in messages:
    handle_new_message(None, lambda: msg)
