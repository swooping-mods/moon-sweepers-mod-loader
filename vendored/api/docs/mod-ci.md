# CI for a mod repository

Each mod repository owns its build, tests, assets and release. Pin an API snapshot under `vendored/api/` and commit the content lock. Use installed tooling in CI; resolve and review any external build dependencies separately.

After building a payload and its author manifest, run:

```sh
PYTHONPATH=vendored/api/python python3 -m moon_mod_api pack manifest.json payload/ artifacts/my-mod.msmod
PYTHONPATH=vendored/api/python python3 -m moon_mod_api validate artifacts/my-mod.msmod
sha256sum artifacts/my-mod.msmod > artifacts/SHA256SUMS
```

Run feature checks before packaging. Keep game qualification separate from host/ABI tests. A PR job validates and retains an artifact; it receives no Nexus credentials. A reviewed release uses the same immutable artifact, publishes to the mod's existing Nexus file, then proposes a version/checksum/file-ID update to `swooping-mods/moon-sweepers-mod-index`.

API releases never publish every consumer automatically. Consumers update their API snapshot and requalify their own behavior. This avoids coupling unrelated mod releases and avoids giving the API repository credentials for all mods.

Nexus's [official upload action](https://github.com/marketplace/actions/upload-to-nexus-mods) currently uses its v3 API. It adds a version to an existing file and requires `api_key`, `file_id`, `filename` and `version`. The initial mod page/file must exist first. Select and statically review the exact uploader revision before enabling it; use a release-only secret and a reviewed immutable artifact. No uploader is installed or enabled in this local preparation.
