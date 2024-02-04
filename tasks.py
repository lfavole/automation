import datetime as dt
from functools import cache

import custom_requests
from oauth_token import Token

token = Token.from_file("google")
token.ensure_valid()  # type: ignore


@cache
def get_main_list_id():
    data = custom_requests.get_with_pages("https://tasks.googleapis.com/tasks/v1/users/@me/lists", token=token)

    for task_list in data:
        if task_list["title"] == "Mes tâches":
            return task_list["id"]

    raise ValueError("Can't get main list ID")


def add_task(title, notes="", due: dt.date | dt.datetime | None = None, list_id=None):
    list_id = list_id or get_main_list_id()

    post_data = {
        "title": title,
        "notes": notes[:8192],
    }
    if due:
        post_data["due"] = f"{due.date() if isinstance(due, dt.datetime) else due}T00:00:00Z"
    print(post_data)

    data = custom_requests.post(
        f"https://tasks.googleapis.com/tasks/v1/lists/{list_id}/tasks",
        json=post_data,
        token=token,
    ).json()
    return data["id"]
