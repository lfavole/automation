import imaplib

from get_secrets import get_secret
from handle_messages import defer, handle_messages_list

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


handle_messages_list("gmx", [(None, defer(message)) for message in messages])

# for msg in messages:
#     handle_new_message(None, defer(msg))
