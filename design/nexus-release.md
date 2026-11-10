# Nexus release path

Nexus Mods is the intended primary player download portal. GitHub owns code, Issues, PRs and candidate builds. This plan does not activate publishing.

A PR runs host checks without publisher secrets. The manual `release-candidate` workflow verifies the pinned API, runs host checks, builds the native loader and retains the portable source ZIP and SHA256SUMS. Qt/game qualification is recorded separately; the candidate is not a native standalone GUI executable.

Before a public release, create/select the loader's Nexus page and initial file. Use the exact candidate archive whose hash was reviewed. Nexus's [official upload action](https://github.com/marketplace/actions/upload-to-nexus-mods) adds a new version of an existing file through its v3 API. It requires `api_key`, `file_id`, `filename` and `version`; a new mod page/initial file cannot be inferred from this preparation.

The eventual release job should take its version from the built candidate, consume the reviewed artifact by digest, and use the chosen Nexus file ID with a release-scoped `NEXUSMODS_API_KEY`. Statically inspect and pin the exact action revision before enabling it. Keep publication outside pull-request jobs. Treat index updates as reviewed metadata changes after a successful upload, not as a side effect of an API release.

Each mod follows the same flow in its owning repository using the API packager. A `.msmod` package already is a ZIP-format artifact; preserve the bytes when using an upload filename accepted by Nexus. Record the filename actually offered to users and retain a `.msmod` filename for local importer use. Do not silently repackage after checksum review.

No Nexus action or secret is configured locally. Missing page/file IDs and the uploader revision are rollout decisions, not hidden CI prerequisites. The included GitHub actions only check source and retain candidate artifacts.
