"""The main entry point to run this program."""

import datetime as dt
import re
from itertools import chain
from typing import Iterable

from check_gmail_emails import get_gmail_emails
from check_gmx_emails import get_gmx_emails
from email_utils import Message
from todoist import Comment, SyncStatus, Task

status: SyncStatus | None = None


def handle_message_list(messages: Iterable[Message]):
    """
    Compare a message list with the message IDs stored on disk and call the
    `handle_new_message` and `handle_deleted_message` functions.
    """
    global status

    if status is None:
        status = SyncStatus(["items", "notes"])

    tasks = Task.all(status)

    # New messages
    for message in messages:
        print(f"Message: {message.hashed_id}")
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

        # Set the due date 7 days after the received date
        # If we received the message after 19:00, add one more day
        due_date = dt.datetime.combine(
            message.date.date() + dt.timedelta(days=8 if message.date.hour >= 19 else 7),
            dt.time(9, 0, 0),
        )

        # If it's a new message, add it to the tasks list, otherwise update the already existing task
        task = Task(
            f"Répondre à {message.sender}",
            f"{message.subject}\n\n{message.body}"[:16383],
            due_date,
            status=status,
            _id=old_task_id,
        )
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

        print()

    # Deleted messages

    # Hashed IDs of messages for which the task has been closed
    closed_tasks_hashed_message_ids: list[str] = []

    for task in tasks:
        for comment in task.get_all_comments():
            # Search for the ID
            match = re.match(r"^ID : (.*?)$", comment.content)
            if not match:
                continue
            hashed_id = match[1]
            # If the ID is in the comment's content, stop here
            if hashed_id in comment.content:
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

    status.sync()


if __name__ == "__main__":
    handle_message_list(chain(get_gmail_emails(), get_gmx_emails()))
