import datetime as dt
from dataclasses import dataclass
from typing import Self

import custom_requests
from oauth_token import Token

token = Token.from_file("todoist")


@dataclass
class Task:
    """A Todoist task."""

    id: str
    title: str
    description: str
    due: dt.datetime | None

    @classmethod
    def from_todoist(cls, data) -> Self:
        """Create a `Task` from the data provided by Todoist."""
        return cls(
            data["id"],
            data["content"],
            data["description"],
            dt.datetime.fromisoformat(data["due"]["datetime"]) if data["due"] else None,
        )

    @classmethod
    def all(cls):
        """Return the list of all tasks."""
        return (
            cls.from_todoist(data)
            for data in custom_requests.get(
                "https://api.todoist.com/rest/v2/tasks",
                token=token,
            ).json()
        )

    def save(self):
        """Add the current task to the default list."""
        data = custom_requests.post(
            "https://api.todoist.com/rest/v2/tasks",
            json={
                "content": self.title,
                "description": self.description,
                "due_datetime": str(self.due) if self.due else None,
            },
            token=token,
        ).json()
        self.id = data["id"]

    def close(self):
        """Close the current task."""
        custom_requests.post(
            f"https://api.todoist.com/rest/v2/tasks/{self.id}/close",
            token=token,
        )
