"""Inspect staged/tracked content without printing private matches."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ALLOWED_ROOTS = {"src", "tests", "configs", "scripts", "docs", "site", ".github", "assets"}
ALLOWED_FILES = {"README.md", "README.zh-CN.md", "LICENSE", "THIRD_PARTY.md", "environment.yml",
                 "pyproject.toml", ".env.example", ".gitignore", ".gitattributes"}
PRIVATE_PATTERNS = [r"/data/user/", r"[A-Za-z0-9_-]+\.hpc\.[A-Za-z0-9.-]+", r"TYPESAFE_API_KEY\s*=\s*[^\s#]",
                    r"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----",
                    r"github_pat_[A-Za-z0-9_]{20,}", r"gh[pousr]_[A-Za-z0-9]{30,}"]


def main():
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=ROOT).decode().split("\0")
    problems = []
    for name in filter(None, names):
        path = PurePosixPath(name)
        if path.parts[0] not in ALLOWED_ROOTS and name not in ALLOWED_FILES:
            problems.append(f"unexpected file: {name}")
        if any(part in {"runs", "artifacts", "private", "runtime", "__pycache__", ".git"} for part in path.parts):
            problems.append(f"private/generated directory: {name}")
        if path.name.startswith(".env") and name != ".env.example":
            problems.append(f"environment file: {name}")
        if name.startswith("assets/panda/") and path.name not in {"LICENSE", "manifest.json"}:
            problems.append(f"unapproved downloaded asset: {name}")
        # Inspect index bytes, not an untracked working-tree substitute.
        data = subprocess.check_output(["git", "show", ":" + name], cwd=ROOT)
        mode = subprocess.check_output(["git", "ls-files", "--stage", "--", name], cwd=ROOT).decode().split()[0]
        if mode == "120000":
            problems.append(f"symlink not allowed in release: {name}")
        if len(data) > 15 * 1024 * 1024:
            problems.append(f"oversized file: {name}")
        if path.suffix not in {".jpg", ".png", ".mp4"} and name != "scripts/check_publication.py":
            text = data.decode("utf-8", errors="replace")
            patterns = PRIVATE_PATTERNS
            if name == "tests/test_credentials.py":
                text = text.replace("TYPESAFE_API_KEY='test-only'", "").replace("TYPESAFE_API_KEY=file-test", "")
            if any(re.search(pattern, text) for pattern in patterns):
                problems.append(f"private data pattern: {name}")
    if problems:
        raise SystemExit("\n".join(problems))
    print(f"Publication checks passed for {len(list(filter(None, names)))} indexed files")


if __name__ == "__main__":
    main()
