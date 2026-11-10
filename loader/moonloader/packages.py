"""Compatibility import; the pinned API owns package validation and resolution."""
from moon_mod_api.packages import (
    SCHEMA, MAX_FILES, MAX_BYTES, MAX_NATIVE_MODS,
    validate, png_icon, examine, install, installed, resolve,
)
