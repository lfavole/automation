"""Utility functions to manage Todoist objects."""

import abc
import datetime as dt
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Self

import custom_requests
from oauth_token import Token


def to_json(data):
    """Return the compact JSON representation of an object."""
    if isinstance(data, Iterable) and not isinstance(data, dict):
        data = list(data)
    return json.dumps(data, separators=(",", ":"))


# https://developer.todoist.com/sync/v9/#payload-size
MAX_SIZE = 1_048_576
# https://developer.todoist.com/sync/v9/#maximum-sync-commands
MAX_COMMANDS = 100


@dataclass
class SyncStatus:
    """The status of a Todoist sync."""

    # The resource types that we want to receive
    resource_types: list[str] = field(default_factory=lambda: ["all"])
    # The pending commands (we use a dict to avoid duplicate actions)
    commands: dict[str, Any] = field(init=False, default_factory=dict)
    # The objects that have temporary IDs that will be mapped to real IDs
    temp_ids: dict[str, "TodoistObject"] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.file = Path(__file__).parent / f"cache/todoist_status_{'_'.join(self.resource_types)}.json"
        if self.file.exists():
            self.data = json.loads(self.file.read_text("utf-8"))
        else:
            self.data: dict[str, Any] = {"sync_token": "*"}
        self.sync()

    def sync(self):
        """Sync the changes with the Todoist API."""
        data = custom_requests.post(
            "https://api.todoist.com/sync/v9/sync",
            data={
                "sync_token": self.data["sync_token"],
                "resource_types": to_json(self.resource_types),
                "commands": to_json(self.commands.values()),
            },
            token=Token.for_provider("todoist"),
        ).json()
        for key, value in data.items():
            if key in ("sync_status", "temp_id_mapping", "sync_token", "full_sync") or not isinstance(value, list):
                self.data[key] = value
                continue

            for item in value:
                self.data.setdefault(key, [])
                to_delete: list[int] = []
                for i, old_item in enumerate(self.data[key]):
                    if old_item["id"] == item["id"]:
                        if item["is_deleted"]:
                            to_delete.append(i)
                        else:
                            self.data[key][i] = item
                        break
                else:
                    self.data[key].append(item)
                for i in to_delete[::-1]:
                    del self.data[key][i]

        for temp_id, id in self.data["temp_id_mapping"].items():
            self.temp_ids[temp_id]._id = id

        sync_status = self.data.setdefault("sync_status", {})

        self.temp_ids = {}
        self.commands = {}

        del self.data["sync_status"]
        del self.data["temp_id_mapping"]

        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(to_json(self.data))

        for id, value in sync_status.items():
            if value == "ok":
                continue
            raise RuntimeError(f"Sync operation {id} failed with error code {value['error_code']} ({value['error']})")

    def add_command(self, obj: "TodoistObject", obj_type: str, args: dict[str, Any] | None = None):
        """Add a command to be synced with the Todoist API."""
        # Generate an temporary ID by accessing the property; if the object has one, save it
        if obj.temp_id:
            self.temp_ids[obj.temp_id] = obj
        to_add = {
            "type": obj_type,
            **({"temp_id": obj.temp_id} if obj.temp_id else {}),
            "uuid": str(uuid.uuid4()),
            "args": {
                **({"id": obj.id} if obj.id else {}),
                **(args or {}),
            },
        }
        # If this object exceeds the maximum size, raise an error
        len_to_add = len(to_json(to_add)) + (1 if self.commands else 2)  # length of the comma or brackets
        if len_to_add > MAX_SIZE:
            raise ValueError("Payload too big")
        # If all the commands will exceed the maximum size or if there are too many commands, sync now
        if len(to_json(self.commands.values())) + len_to_add >= MAX_SIZE or len(self.commands) >= MAX_COMMANDS:
            self.sync()
        self.commands[obj.id] = to_add


# https://stackoverflow.com/a/72715549
@dataclass(kw_only=True)
class TodoistObject:
    """An object on Todoist"""

    status: SyncStatus
    _id: str | None = None
    _temp_id: str | None = None
    _saving: bool = False

    @property
    def temp_id(self):
        """The temporary ID of the current object. If not already specified, it is generated when accessed."""
        if self._id:
            return None
        if not self._temp_id:
            self._temp_id = str(uuid.uuid4())
            if not self._saving:
                self.save()
        return self._temp_id

    @property
    def id(self) -> str:
        """
        The ID or temporary ID of the current object. A temporary ID is created if needed.

        This is the recommended way to refer to an object.
        """
        return self._id or self.temp_id  # type: ignore

    def has_id(self):
        """Return True if the element already has an ID or a temporary ID, False otherwise."""
        return bool(self._id or self._temp_id)

    @property
    @abc.abstractmethod
    def object_type(self) -> str:
        """The Todoist object type of this object."""

    @property
    @abc.abstractmethod
    def data(self) -> dict[str, Any]:
        """The Todoist data representation associated with this object."""

    def save(self):
        """Add or update the current object."""
        self._saving = True
        if self._id:
            self.status.add_command(self, f"{self.object_type}_update", {"id": self._id, **self.data})
        else:
            self.status.add_command(self, f"{self.object_type}_add", self.data)
        self._saving = False


@dataclass
class Task(TodoistObject):
    """A Todoist task."""

    title: str
    description: str
    due: dt.datetime | None = None
    priority: int = 1

    object_type = "item"  # type: ignore

    @property
    def data(self):
        return {
            "content": self.title,
            "description": self.description,
            "due": {"date": self.due.isoformat()} if self.due else None,
            "priority": self.priority,
        }

    @classmethod
    def from_todoist(cls, data, status: SyncStatus) -> Self:
        """Create a `Task` from the data provided by Todoist."""
        return cls(
            status=status,
            _id=data["id"],
            title=data["content"],
            description=data["description"],
            due=dt.datetime.fromisoformat(data["due"]["date"]) if data["due"] else None,
        )

    @classmethod
    def all(cls, status: SyncStatus):
        """Return the list of all tasks."""
        return [cls.from_todoist(data, status) for data in status.data["items"]]

    def close(self):
        """Close the current task."""
        self.status.add_command(self, "item_close")

    def delete(self):
        """Delete the current task."""
        self.status.add_command(self, "item_delete")

    def get_all_comments(self):
        """Return all the comments on the current task."""
        ret: list[Comment] = []
        for item in self.status.data["notes"]:
            if item["item_id"] == self.id:
                ret.append(Comment(_id=item["id"], status=self.status, task=self, content=item["content"]))
        return ret


@dataclass
class Comment(TodoistObject):
    """A comment on a Todoist task."""

    task: Task
    content: str

    object_type = "note"  # type: ignore

    @property
    def data(self):
        return {"item_id": self.task.id, "content": self.content}
