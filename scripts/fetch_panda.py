"""Fetch only the pinned, Apache-2.0 Franka assets; never download at simulation startup."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

REVISION = "822c2d8f877dd166c5b7d3c9f7e3c3b6589473b7"
REPOSITORY = "google-deepmind/mujoco_menagerie"
ROOT = Path(__file__).resolve().parents[1] / "assets" / "panda"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "jev-vla-sim"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def main():
    tree = json.loads(fetch(f"https://api.github.com/repos/{REPOSITORY}/git/trees/{REVISION}?recursive=1"))
    prefix = "franka_emika_panda/"
    entries = [item for item in tree["tree"] if item["type"] == "blob"
               and item["path"].startswith(prefix)
               and (item["path"][len(prefix):] in {"panda.xml", "LICENSE", "README.md"}
                    or item["path"].startswith(prefix + "assets/"))]

    def download(item):
        relative = item["path"][len(prefix):]
        target = ROOT / relative
        data = target.read_bytes() if target.is_file() else b""
        def git_hash(b):
            return hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
        if git_hash(data) != item["sha"]:
            data = fetch(f"https://raw.githubusercontent.com/{REPOSITORY}/{REVISION}/{item['path']}")
            if git_hash(data) != item["sha"]:
                raise RuntimeError(f"asset checksum mismatch: {relative}")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        return relative, hashlib.sha256(data).hexdigest()

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        hashes = dict(pool.map(download, entries))
    manifest = {"repository": REPOSITORY, "revision": REVISION, "license": "Apache-2.0",
                "files": hashes}
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Verified {len(hashes)} Panda files at {ROOT}")


if __name__ == "__main__":
    main()
