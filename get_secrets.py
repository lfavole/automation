"""A dict that returns secrets from environment variables or from the `.env` file."""

import os
from pathlib import Path

NOT_PROVIDED = object()


class Secrets(dict):
    """A dict that returns secrets from the `.env` file or from environment variables."""

    def __init__(self):
        super().__init__()

        self.file = Path(__file__).parent / ".env"
        if self.file.exists():
            with self.file.open() as f:
                for line in f:
                    key, _, value = line[:-1].partition("=")
                    self[key] = value

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except KeyError:
            return os.environ[key]

    def get(self, key, default):
        if key not in self:
            return os.environ.get(key, default)
        return super().get(key, default)

    def setdefault(self, key, default):
        if key not in self and key in os.environ:
            return os.environ[key]
        return super().setdefault(key, default)

    def pop(self, key):
        ret = super().pop(key)
        self.save()
        return ret

    def popitem(self):
        ret = super().popitem()
        self.save()
        return ret

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.save()

    def save(self):
        """Save the secrets to the `.env` file."""
        new_file = self.file.with_name(self.file.name + ".new")
        with new_file.open("w") as f:
            for key, value in self.items():
                f.write(f"{key}={value}\n")
        new_file.rename(self.file)


secrets = Secrets()
