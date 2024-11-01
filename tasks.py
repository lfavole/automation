"""Utility functions to manage Todoist tasks."""

import datetime as dt
from dataclasses import dataclass
from typing import Self

import custom_requests
from oauth_token import Token

token = Token.from_file("todoist")


@dataclass
class Task:
    """A Todoist task."""

    id: str | None
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
        return [
            cls.from_todoist(data)
            for data in custom_requests.get(
                "https://api.todoist.com/rest/v2/tasks",
                token=token,
            ).json()
        ]

    def save(self):
        """Add the current task to the default list or update it."""
        data = custom_requests.post(
            "https://api.todoist.com/rest/v2/tasks" + ("/" + self.id if self.id else ""),
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

    def delete(self):
        """Delete the current task."""
        custom_requests.delete(
            f"https://api.todoist.com/rest/v2/tasks/{self.id}",
            token=token,
        )

    def get_all_comments(self):
        """Return all the comments on the current task."""
        data = custom_requests.get(
            "https://api.todoist.com/rest/v2/comments",
            params={"task_id": self.id},
            token=token,
        ).json()
        ret: list[Comment] = []
        for item in data:
            ret.append(Comment(item["id"], item["task_id"], item["content"]))
        return ret


@dataclass
class Comment:
    """A comment on a Todoist task."""

    id: str | None
    task_id: str
    content: str

    def save(self):
        """Add or update the current comment."""
        data = custom_requests.post(
            "https://api.todoist.com/rest/v2/comments",
            params={"task_id": self.task_id, "content": self.content},
            token=token,
        ).json()
        self.id = data["id"]
