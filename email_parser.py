import datetime as dt
import re
from typing import Any

from email_utils import Message
from todoist import SyncStatus, Task


class EmailParser:
    """A parser that finds important information in emails."""

    DEFAULT_TIME = dt.time(9, 0, 0)

    @classmethod
    def parse_email(cls, message: Message, status: SyncStatus):
        """Parse an email and return a task that corresponds to it."""
        # Set the due date 7 days after the received date
        # If we received the message after 19:00, add one more day
        due_date = dt.datetime.combine(
            message.date.date() + dt.timedelta(days=8 if message.date.hour >= 19 else 7),
            cls.DEFAULT_TIME,
        )
        params = {
            "title": f"Répondre à {message.sender}",
            "description": f"**{message.subject}**\n\n{message.body}"[:16383],
            "due": due_date,
            "status": status,
        }

        if "List-ID" in message.headers:
            params.update(cls.parse_newsletter(message))

        if "Your SSL certificate" in message.subject and "issued" not in message.subject:
            params.update(cls.parse_infinityfree(message))

        if "workflow" in message.subject and "disabled" in message.subject:
            params.update(cls.parse_github_workflow(message))

        if isinstance(params["due"], dt.date):
            params["due"] = dt.datetime.combine(params["due"], cls.DEFAULT_TIME)

        return Task(**params)

    @classmethod
    def parse_newsletter(cls, message: Message):
        """Parse a newsletter email: write "Read" instead of "Reply" in the task title."""
        return {
            "title": f"Lire le message de {message.sender}",
        }

    @classmethod
    def parse_infinityfree(cls, message: Message):
        """Parse an InfinityFree certificate email: get the date and set the task as urgent."""
        # Find the concerned website
        match = re.search(r"Your SSL certificate for (.*?) ", message.subject)
        if not match:
            site = "du site InfinityFree"
        else:
            site = f"de {match[1]}"

        ret: dict[str, Any] = {
            "title": f"Mettre à jour le certificat {site}",
            # Set the task as urgent
            "priority": 4,
        }

        # Find the expiry date
        match = re.search(r"will expire on (?:\*\*)?(.*?)(?:\*\*)?", message.body)
        if match:
            date = dt.date.fromisoformat(match[1])
        elif "has expired" in message.subject:
            # If the certificate has already expired, it happened when we received the email
            date = message.date.date()
        else:
            return ret

        ret["due"] = date

        # Find the link that points to the certificate
        match = re.search(r"View SSL Certificate: (https?://.*)", message.body)
        if match:
            ret["description"] = f"[Voir le certificat]({match[1]})"

        return ret

    @classmethod
    def parse_github_workflow(cls, message: Message):
        """Parse a "scheduled workflow will be disabled" email."""
        if "will be" in message.subject:
            # We can receive an email one week before...
            date = message.date.date() + dt.timedelta(days=7)
        else:
            # ...or the same day
            date = message.date.date()

        workflow_name = "GitHub"
        ret: dict[str, Any] = {
            "due": date,
            # Set the task as urgent
            "priority": 4,
        }

        # Find the workflow name and add it in the title
        match = re.search(r'The "(.*?)" workflow in (.*?) ', message.subject)
        if match:
            workflow_name = f'"{match[1]}" dans {match[2]}'

        ret["title"] = f"Réactiver le workflow {workflow_name}"

        # Find the link that points to the workflow
        match = re.search(r"https?://github.com/.*", message.body)
        if match:
            ret["description"] = f"[Voir le workflow {workflow_name}]({match[0]})"

        return ret
