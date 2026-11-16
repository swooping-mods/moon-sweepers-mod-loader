#!/usr/bin/env python3
"""Run focused offline checks and retain the current verification receipt."""
import argparse
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    sys.path.insert(0, str(ROOT / "tools"))
    if (ROOT / "tools/check_snapshot.py").exists():
        from check_snapshot import check
        check()
    from check_native_sdk import check as check_native_sdk
    check_native_sdk()
    from check_managed_sources import check as check_managed_sources
    check_managed_sources()
    from mod_bundle import payload
    payload()
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    receipt = {"success": result.wasSuccessful(), "tests_run": result.testsRun,
               "failures": len(result.failures), "errors": len(result.errors),
               "skipped": [(t.id(), why) for t, why in result.skipped],
               "excluded": [], "game_started": False,
               "limits": ["No game, Wine, native Windows or co-op execution", "No Nexus/GitHub publication"]}
    out = ROOT / "artifacts"
    out.mkdir(exist_ok=True)
    (out / "checks.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return 0 if result.wasSuccessful() else 1

if __name__ == "__main__":
    raise SystemExit(main())
