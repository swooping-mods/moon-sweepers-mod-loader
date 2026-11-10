# Organization source push

Date: 2026-11-10. The user authorized pushing the reviewed API and loader repositories under `swooping-mods` and explicitly requested `gh`. The private GitHub target is https://github.com/swooping-mods/moon-sweepers-mod-loader. The installed GitHub CLI creates/inspects the repository; Git transfers the committed branch using existing host authentication.

Initial source commit: `76938c3794a35ca78768c95c8845f16cfcc0b9e7`. `origin` targets this organization repository and `main` tracks `origin/main`. The index repository is outside this push. The source destination is private, matching the original development repository.

The reviewed loader source is published. All 39 local checks pass, including three compiled native host checks and two Qt interaction cases in headless Gamescope. The API snapshot remains pinned; no gameplay mod binaries or private data were added.

Only committed reviewed source and this task's explicit documentation updates are pushed. Generated output, game files, saves, credentials and concurrent uncommitted feature work stay local. No PR or release is created.

Final remote branch SHA, local SHA, visibility, workflow status and preserved working-tree state are recorded in ignored `artifacts/organization-push.json`. Local checks are recorded in `artifacts/checks.json`. Hosted CI excludes the loader's two Qt tests, which passed locally. Game, Wine, native Windows and co-op were not run for publication.
