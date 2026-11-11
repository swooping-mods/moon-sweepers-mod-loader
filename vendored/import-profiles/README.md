# Download recognition inputs

These profiles convert explicitly selected local downloads into the existing
checked package format. They never download, install a runtime or execute a mod.

`marssweepers.json` retains the existing MarsSweepers 0.6.1 wrapper manifest from
the Moon Sweepers External Mods project. Its eight external payload hashes bind
the original user-supplied DLL and seven voice WAVs. Those files and upstream
source are absent from this repository. The user supplies their own download;
no redistribution rights for MarsSweepers are inferred.

The three support inputs under `marssweepers/` are the original integration's
compatibility companion, wrapper PNG artwork and readme. Their SHA-256 values
are pinned in the profile manifest. The companion's owning source is
`moon-sweepers-external-mods/mods/marssweepers/MarsCompatibility.cs`, SHA-256
`51d30e67583b36a2c129f81618020e5de9c5546fe8630f2579914b81dbe2dbcf`;
its source-current compiled DLL is
`92386a98b76b8efd1e1f272978672f9726f5d5c5304fe985481f13908083f602`.
It verifies the exact Mars DLL, clears destroyed Unity wind/logo caches and marks
Mars save rows through in-process Harmony hooks. No networking, shell execution,
installer, persistence or credentials are part of that companion.

The 2026-11-11 bounded review reused the source-current build and previous exact
candidate/adapter review, inspected the original companion and hash closure, and
ran the standard static scanner and ClamAV on these actual support inputs.
Static scanning reported two resolved leads (the inert provenance URL and
expected managed DLL), with zero coverage gaps. ClamAV 1.5.4 scanned four files
with exit 0 and no detections; DB28158 dated 2026-10-19 was stale and was not
refreshed. Private full receipts remain under ignored
`artifacts/import-profile-review/`. This review admits offline import, packaging
and no-game desktop checks. No new native Windows, loaded-world or co-op claim
is made. No project license is assigned.
