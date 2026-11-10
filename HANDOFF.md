# Current milestone: private organization source push

Objective: push the reviewed moon-sweepers-mod-loader source to `swooping-mods`, as authorized by the user, using the installed GitHub CLI.

Decisions: use the private repository https://github.com/swooping-mods/moon-sweepers-mod-loader, preserving the original private visibility. Keep `main` tracking `origin/main`. Keep the index local and preserve concurrent API feature work. No PR, Nexus release, project license or additional repository is included.

State: The reviewed loader source is published. All 39 local checks pass, including three compiled native host checks and two Qt interaction cases in headless Gamescope. The API snapshot remains pinned; no gameplay mod binaries or private data were added. Documentation now points at the organization repository. Initial source commit: `76938c3794a35ca78768c95c8845f16cfcc0b9e7`. Final branch/privacy verification is recorded outside specs under `artifacts/organization-push.json`.

Next action: continue development in this checkout. Nexus pages, file IDs, uploader credentials and hosted-index integration remain separate rollout work; game, Wine, native Windows and co-op qualification were not rerun for this push.

Evidence: `verification/organization-push.md`; `artifacts/organization-push.json`; `artifacts/checks.json`; `vendored/extraction.json`; `specs/_readme.md`.
