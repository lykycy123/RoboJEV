from __future__ import annotations

import os
from pathlib import Path


def load_key_file(path: str | Path = ".env") -> bool:
    """Read ONLY TYPESAFE_API_KEY. Never execute shell text or expand variables."""
    if os.environ.get("TYPESAFE_API_KEY"):
        return True
    path = Path(path)
    if not path.is_file():
        return False
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip().removeprefix("export ")
        key, sep, value = line.partition("=")
        if sep and key.strip() == "TYPESAFE_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            if value:
                os.environ["TYPESAFE_API_KEY"] = value
                return True
    return False
