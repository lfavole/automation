import json
import os
from pathlib import Path

NOT_PROVIDED = object()
secrets_json = Path(__file__).parent / "secrets.json"
secrets_json_data = {}
if secrets_json.exists():
    secrets_json_data = json.loads(secrets_json.read_text())


def get_secret(name, default=NOT_PROVIDED):
    ret = os.getenv(name)
    if ret is not None:
        return ret

    ret = secrets_json_data.get(name)
    if ret is not None:
        return ret

    if default is not NOT_PROVIDED:
        return default
    raise ValueError(f"Can't get secret '{name}'")
