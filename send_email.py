import smtplib
from email.message import EmailMessage

from get_secrets import secrets


def send_email(to, subject, message, html_message=""):
    """Send an email."""

    msg = EmailMessage()
    msg.set_content(message)
    if html_message:
        msg.add_alternative(html_message, subtype="html")
    msg["Subject"] = subject
    msg["From"] = secrets["GMX_USER"]
    msg["To"] = to

    with smtplib.SMTP_SSL("mail.gmx.com", 465) as server:
        server.login(secrets["GMX_USER"], secrets["GMX_PASSWORD"])
        server.send_message(msg)
