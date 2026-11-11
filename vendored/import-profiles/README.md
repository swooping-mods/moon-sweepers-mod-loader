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
`moon-sweepers-external-mods/mods/marssweepers/`. Current source hashes are
`693f8519b9a8ccc5c57534c2282ce94d82f2ea61d5575cd2910083698d320005`
(`MarsCompatibility.cs`),
`20401fd5b0c4d3f2da3ab2c0f8663a00464e2c5ccc1e9362310526a289b6dea1`
(`MarsMultiplayer.cs`) and
`fa091621476ea338585ece6f3842de5d864b7c221a888e62c0b01444e8e6ae9c`
(`MarsNetworkPolicy.cs`); the compiled DLL is
`3ff857adeffd4cc74dedf2bed521e1cff7aa932089d401169501b5fa0b472037`.
It verifies the exact Mars DLL, clears destroyed Unity wind/logo caches and marks
Mars save rows. Multiplayer repairs bound packets and gzip expansion, authenticate
senders, retry initial state and recover receive polling. They also check host
version metadata, share host storm settings among wrapped peers and keep the
`data test` diagnostic from sending the OS username. Channel 7/protocol 1 and the
upstream DLL remain unchanged; an unmodified peer without the companion cannot
be forced to perform its admission checks. There is no installer, shell command,
credential access or persistent local configuration write in these repairs.

The 2026-11-11 bounded review reused the source-current build and previous exact
candidate/adapter review, inspected the original companion and hash closure, and
ran the standard static scanner and ClamAV on these actual support inputs.
Static scanning reported two resolved leads (the inert provenance URL and
expected managed DLL), with zero coverage gaps. ClamAV 1.5.4 scanned four files
with exit 0 and no detections; DB28158 dated 2026-10-19 was stale and was not
refreshed. Private full receipts remain under ignored
`artifacts/import-profile-review/`. This review admits offline import, packaging
and no-game desktop checks. That import-only review made no new native Windows,
loaded-world or co-op claim. No project license is assigned.

The refreshed companion passes 48 executable policy/callback regression
assertions and its actual compile/package checks in the owning external-mods
project. Private solo world replay of package SHA-256
`1cf27a2184d21d5236ef8953c4952409b823dc14e295570b39d2eced2b1d2015`
passed startup, movement, save/menu/reload and Unity shutdown with the existing
.NET 6 development control. Real co-op and the maintained release runtime are
separate qualification gates. Current local receipts are retained under ignored
`.local/release-0.2.1/` and the workshop's `artifacts/bepinex-release-021/`.
