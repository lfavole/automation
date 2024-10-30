import json
import os
from pathlib import Path
from typing import overload

NOT_PROVIDED = object()

secrets_json = Path(__file__).parent / "secrets.json"
secrets_json_data = {}
if secrets_json.exists():
    secrets_json_data = json.loads(secrets_json.read_text())


@overload
def get_secret(name: str, default=NOT_PROVIDED) -> str:
    pass


@overload
def get_secret(name: str, default: str) -> str:
    pass


def get_secret(name: str, default=NOT_PROVIDED):
    """
    Returns a secret from environment variables or secrets.json file.
    """
    ret = os.getenv(name)
    if ret is not None:
        return ret

    ret = secrets_json_data.get(name)
    if ret is not None:
        return ret

    if default is not NOT_PROVIDED:
        return default
    raise ValueError(f"Can't get secret '{name}'")
