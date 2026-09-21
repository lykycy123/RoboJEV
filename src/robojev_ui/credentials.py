from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path


class Credentials:
    def __init__(self, root: Path, config_home: Path):
        self.root = root
        self.path = config_home / "credentials.json"
        self.key = None
        self.disabled = False
        self.lock = threading.RLock()
        self.secrets = set()

    def resolve(self):
        with self.lock:
            if self.disabled:
                return None, "none"
            if self.key:
                return self.key, "session"
            if self.path.exists():
                try:
                    key = json.loads(self.path.read_text()).get("key")
                except (OSError, ValueError, AttributeError):
                    key = None
                if key:
                    self.secrets.add(key)
                    return key, "saved"
            key = os.environ.get("TYPESAFE_API_KEY")
            if key:
                self.secrets.add(key)
                return key, "environment"
            path = self.root / ".env"
            if path.is_file():
                for line in path.read_text(encoding="utf-8").splitlines():
                    name, sep, value = line.strip().removeprefix("export ").partition("=")
                    if sep and name.strip() == "TYPESAFE_API_KEY":
                        value = value.strip()
                        if len(value) > 1 and value[0] == value[-1] and value[0] in "\"'":
                            value = value[1:-1]
                        if value:
                            self.secrets.add(value)
                            return value, "project .env"
            return None, "none"

    def status(self):
        key, source = self.resolve()
        return {"available": bool(key), "source": source, "remembered": self.path.exists()}

    def set(self, key, remember=False):
        if not key.strip() or len(key) > 4096 or any(c.isspace() for c in key):
            raise ValueError("Key must be nonempty and contain no whitespace")
        with self.lock:
            self.disabled = False
            self.secrets.add(key)
            self.key = key
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if remember:
                temporary = self.path.with_suffix(".tmp")
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as f:
                    json.dump({"key": key}, f)
                temporary.chmod(0o600)
                temporary.replace(self.path)
                self.key = None
            else:
                self.path.unlink(missing_ok=True)

    def clear(self):
        with self.lock:
            self.key = None
            self.disabled = True
            self.path.unlink(missing_ok=True)

    def redact(self, text):
        with self.lock:
            for key in sorted(self.secrets, key=len, reverse=True):
                text = text.replace(key, "[REDACTED]")
        return re.sub(r"(?i)Bearer\s+[^\s\"']+", "Bearer [REDACTED]", text)
