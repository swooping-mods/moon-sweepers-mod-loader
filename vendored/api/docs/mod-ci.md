# CI for a mod repository

Each mod repository owns its build, tests, assets and release. Pin an API snapshot under `vendored/api/` and commit the content lock. Use installed tooling in CI; resolve and review any external build dependencies separately.

After building a payload and its author manifest, run:

```sh
PYTHONPATH=vendored/api/python python3 -m moon_mod_api pack manifest.json payload/ artifacts/my-mod.msmod
PYTHONPATH=vendored/api/python python3 -m moon_mod_api validate artifacts/my-mod.msmod
sha256sum artifacts/my-mod.msmod > artifacts/SHA256SUMS
```

Run feature checks before packaging. CI can validate and retain the resulting
artifact without access to publishing credentials. Host/ABI checks and in-game
qualification establish different behavior.

Consumers pin their own API snapshot and choose when to update it. API releases
do not publish consumers automatically.
