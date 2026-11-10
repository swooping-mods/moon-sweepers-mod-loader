"""Verify that the included API matches its reviewed content lock."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check():
    snapshot = ROOT / "vendored/api"
    lock = json.loads((snapshot / "snapshot.json").read_text())
    if lock["schema"] != "moon-api-snapshot/v1" or lock["repository"] != "moon-sweepers-api":
        raise ValueError("Unexpected API snapshot identity")
    actual = {p.relative_to(snapshot).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in snapshot.rglob("*") if p.is_file() and "__pycache__" not in p.parts
              and p.name != "snapshot.json" and p.suffix != ".pyc"}
    if any(p.is_symlink() for p in snapshot.rglob("*")) or actual != lock["files"]:
        raise ValueError("API snapshot differs from its pinned file table")
    print("API snapshot verified:", lock["version"], len(actual), "files")


if __name__ == "__main__":
    check()
