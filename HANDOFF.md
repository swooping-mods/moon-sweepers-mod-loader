# Current milestone: clean local organization repository

Objective: prepare `swooping-mods/moon-sweepers-mod-loader` for user inspection without pushing or publishing.

Decisions: split API/contracts and package tools, desktop/native loader, and metadata-only index into separate repositories. Keep the existing MoonLab native ABI. Pin the loader's first-party API snapshot by file hashes. Keep gameplay mods independently versioned; Nexus is the intended player portal, GitHub owns code/Issues/PRs. Do not assign a project license.

State: clean first-party extraction and focused documentation/specs are prepared. 39 focused local tests pass. CI source checks and manual candidate workflows are defined; neither publishes. The existing development checkout was not modified by this task. Public source/Nexus endpoints remain unassigned; catalog entries remain development-only. See `verification/local-preparation.md` for checks and limits.

Next action: user reviews this repository and the loader's `design/repository-split.md`. After acceptance, repository creation/push, Nexus destinations/credentials and hosted-index integration are separate rollout work. No remote is configured.

Evidence: `vendored/extraction.json`; `verification/local-preparation.md`; `artifacts/checks.json`, `artifacts/qt-checks.log`, `artifacts/build-receipt.json`, `artifacts/portable-smoke.json`, `artifacts/extraction-first-check.json`; `specs/_readme.md`.
