import email
import email.header
import email.policy
import imaplib

from get_secrets import get_secret

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


def get_header(msg, header):
    header_data = email.header.decode_header(msg[header])
    header = email.header.make_header(header_data)
    return str(header)


for msg in messages:
    msg = email.message_from_bytes(msg, policy=email.policy.default)
    subject = get_header(msg, "Subject")
