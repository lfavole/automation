"""The main entry point to run this program."""

import hashlib
import re
import traceback
from pathlib import Path
from typing import Iterable
from urllib.error import HTTPError

from check_gmail_emails import get_gmail_emails
from check_gmx_emails import get_gmx_emails
from email_parser import EmailParser
from email_utils import Message
from get_secrets import secrets
from send_email import send_email
from todoist import Comment, SyncStatus, Task


def send_todoist_error(err: Exception):
    """Send an email with the Todoist sync error message to the user."""
    # If we don't need to send the error, stop here
    if isinstance(err, HTTPError):
        err_to_check = err
        while err_to_check:
            if any(message in str(err) for message in ("Bad Gateway", "Service Unavailable")):
                return
            err_to_check = err_to_check.__cause__

    subject = "An error occurred while adding tasks to Todoist"
    message = f"""\
An error occurred while adding tasks to Todoist:
{type(err).__name__}: {err}

{"".join(traceback.format_exception(err))}
"""
    html_message = f"""\
<!DOCTYPE html>
<html>
<head>
<title>{subject}</title>
</head>
<body>
<p>An error occurred while adding tasks to Todoist:</p>
<p><b>{type(err).__name__}</b>: {err}</p>
<pre>{"".join(traceback.format_exception(err))}</pre>
</body>
</html>
"""
    lock_text = f"{type(err).__name__}: {err}"
    # Remove UUIDs from the error message
    lock_text = re.sub(r"\b[0-9a-f-]{36}\b", "[UUID]", lock_text)
    hash = hashlib.sha256(lock_text.encode()).hexdigest()
    lockfile = Path(__file__).parent / f"cache/error_email_{hash}"
    if lockfile.exists():
        print("Error email already sent")
        return
    lockfile.touch()
    send_email(secrets["GMX_USER"], subject, message, html_message)
    print("Error email sent")


def handle_message_list(messages: Iterable[Message]):
    """
    Compare a message list with the message IDs present in the tasks and call the
    `handle_new_message` and `handle_deleted_message` functions.
    """
    try:
        status = SyncStatus(["items", "notes"])
    except Exception as err:  # pylint: disable=W0718
        if not isinstance(err, HTTPError) or not any(
            message in str(err) for message in ("Bad Gateway", "Service Unavailable")
        ):
            raise  # propagate the error only if we don't send the email
        send_todoist_error(err)

    tasks = Task.all(status)

    seen_hashed_message_ids: list[str] = []

    # New messages
    for message in messages:
        print(f"Message: {message.hashed_id}")
        seen_hashed_message_ids.append(message.hashed_id)
        handle_new_message(message, tasks, status)
        print()

    # Deleted messages
    check_deleted_messages(tasks, seen_hashed_message_ids)

    # Send the changes to Todoist
    try:
        status.sync()
    except Exception as err:  # pylint: disable=W0718
        send_todoist_error(err)


def handle_new_message(message: Message, tasks: list[Task], status: SyncStatus):
    """Handle a new message: create a task and remove the duplicate tasks."""
    # The ID of an already created task about this message
    old_task_id = None
    for task in tasks:
        for comment in task.get_all_comments():
            if message.hashed_id in comment.content:
                if old_task_id is None:
                    # If it's the first task we see, save its ID to edit it
                    print("    Task found")
                    old_task_id = task.id
                else:
                    # Otherwise, delete the task because it's a duplicate
                    task.delete()
                    # Keep our list in sync with Todoist
                    tasks.remove(task)
                    print("    Duplicate task deleted")

    if old_task_id is None:
        print("    New message")

    task = EmailParser.parse_email(message, status)
    task._id = old_task_id
    task.save()
    tasks.append(task)

    if not old_task_id:
        Comment(task, f"ID : {message.hashed_id}", status=status).save()
        print("    Task created")
    else:
        for comment in task.get_all_comments():
            if message.hashed_id in comment.content:
                break
        else:
            Comment(task, f"ID : {message.hashed_id}", status=status).save()
        print("    Task updated")


def check_deleted_messages(tasks: list[Task], seen_hashed_message_ids: list[str]):
    """Check for deleted messages and close or delete the associated tasks."""

    # Hashed IDs of messages for which the task has been closed
    closed_tasks_hashed_message_ids: list[str] = []

    for task in tasks:
        for comment in task.get_all_comments():
            # Search for the ID
            match = re.match(r"^ID : (.*?)$", comment.content)
            if not match:
                continue
            hashed_id = match[1]
            # If the ID is in the seen messages, stop here
            if hashed_id in seen_hashed_message_ids:
                break

            print(f"Deleted message: {hashed_id}")

            if hashed_id not in closed_tasks_hashed_message_ids:
                # If the task hasn't been closed, close it
                closed_tasks_hashed_message_ids.append(hashed_id)
                task.close()
                print("Task closed")
            else:
                # Otherwise, delete it
                task.delete()
                # Keep our list in sync with Todoist
                tasks.remove(task)
                print("Duplicate task deleted")


if __name__ == "__main__":
    emails = []

    try:
        emails.extend(get_gmail_emails())
    except Exception as err:  # pylint: disable=W0718
        emails.append(Message.error(err, "gmail"))

    try:
        emails.extend(get_gmx_emails())
    except Exception as err:  # pylint: disable=W0718
        emails.append(Message.error(err, "gmx"))

    handle_message_list(emails)

    # Remove old error lockfiles
    print("Cleaning up error lockfiles")
    for file in Path(__file__).parent.glob("cache/error_email_*"):
        file.unlink()
