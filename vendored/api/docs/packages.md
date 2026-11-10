# Package contract

`moon_mod_api.packages` is the executable authority for `moon-mod-package/v1`. The loader imports an exact snapshot of that implementation; it does not maintain a second validator.

A `.msmod` is a ZIP containing `manifest.json` and exactly the payload files named in its SHA-256 table. Required manifest fields are `schema`, `id`, `version`, `name`, `summary`, `description`, `author`, `kind`, `abi`, `entry`, `icon`, `requires`, `conflicts`, `claims`, `game` and `files`.

IDs are lowercase hyphenated names, at most 64 characters. Versions use `major.minor.patch` with an optional lowercase prerelease suffix. Icons contain PNG data with dimensions at most 1024 by 1024. Native entries use `MoonLab_ModStart/v1` through `/v5` and a DLL. Companion tools use `PythonZipApp/v1`, a `.pyz`, and no native dependencies/conflicts/claims. The hook guide explains the required roles and marker for v5.

The archive and unpacked payload are limited to 64 MiB, 128 payload files and a 32 KiB manifest. Paths must have one portable spelling; absolute/traversal paths, Windows devices/streams, case collisions, symlinks, encryption and unlisted members fail. Integrity hashes do not authenticate an author or sandbox a native DLL.

`game.id` is `moon-sweepers`, `game.appid` is `5335510`, and `game.hashes` must contain one or more supported executable SHA-256 pins. The loader owns the currently supported game build; mod authors own their declared compatibility. A mod must not infer support merely because the game version string matches.

`resolve` requires explicit dependency selection and yields deterministic dependency-first order. It rejects missing dependencies, cycles, declared conflicts, exclusive hook overlap, duplicate input/physics owners and multiple camera overrides. The capacity is 64 selected native mods; capacity does not imply combined gameplay qualification.

The extraction retains the existing package schema and `MoonLab_*` exported symbols. API package version 0.1.0, C hook ABI 1, native package ABI v5 and the mod's own version are separate version domains.
