"""Compatibility import; the pinned API owns package validation and resolution."""
from moon_mod_api.packages import (
    SCHEMA, MAX_FILES, MAX_BYTES, MAX_NATIVE_MODS, MAX_GAME_MODS,
    MANAGED_KIND, MANAGED_ABI, game_mod, require_available,
    validate, png_icon, examine, install, installed, resolve,
)
from moon_mod_api.runtimes import NATIVE_ABIS
