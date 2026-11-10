"""Compatibility entrypoint for the pinned API package authoring tool."""
import moonloader
from moon_mod_api.pack import pack, main

if __name__ == "__main__":
    raise SystemExit(main())
