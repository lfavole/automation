"""A dict that returns secrets from environment variables or from the `.env` file."""

from pathlib import Path

NOT_PROVIDED = object()


class Secrets(dict):
    def __init__(self):
        self.file = Path(__file__).parent / ".env"
        data = {}
        if self.file.exists():
            with self.file.open() as f:
                for line in f:
                    key, _, value = line[:-1].partition("=")
                    data[key] = value
        super().__init__(data)

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self.save()

    def save(self):
        new_file = self.file.with_name(self.file.name + ".new")
        with new_file.open("w") as f:
            for key, value in self.items():
                f.write(f"{key}={value}\n")
        new_file.rename(self.file)


secrets = Secrets()
