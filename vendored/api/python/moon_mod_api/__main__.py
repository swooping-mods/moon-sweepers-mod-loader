"""Offline command line package authoring and validation."""
import argparse
import json
from pathlib import Path

from .pack import pack
from .packages import examine, validate
from .storage import load


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate", help="Validate a .msmod or manifest JSON")
    check.add_argument("path", type=Path)
    build = commands.add_parser("pack", help="Create an immutable .msmod locally")
    build.add_argument("manifest", type=Path)
    build.add_argument("payload", type=Path)
    build.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.command == "pack":
        print(pack(args.manifest, args.payload, args.output))
    else:
        result = examine(args.path) if args.path.suffix == ".msmod" else validate(load(args.path))
        print(json.dumps({"id": result["id"], "version": result["version"], "valid": True}))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
