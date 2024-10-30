import datetime as dt

from email_utils import Message, hash_message_id
from tasks import Task


def handle_new_message(msg: Message):
    """Handle a new message."""
    due_date = msg.date + dt.timedelta(days=7)

    notes_end = f"\n\nID : {hash_message_id(msg.id)}"

    Task(
        "",
        f"Répondre à {msg.sender}",
        f"{msg.subject}\n\n{msg.body}"[: 16383 - len(notes_end)] + notes_end,
        due_date,
    ).save()
    print("Task created")


def handle_deleted_message(message_id: str):
    """Handle a deleted message."""
    tasks = Task.all()
    for task in tasks:
        if message_id in task.description:
            task.close()
            print("Task closed")
