# Starter mod bundle

| Package | Version | Role |
|---|---|---|
| Squishy Plushie | 0.2.0 | Handpicked toy |
| Futuristic Courier (`futuristic-car`) | 0.2.1 | Handpicked vehicle |
| Power Poles (`manual-power-poles`) | 0.6.1 | Handpicked building |
| Debug Menu | 0.1.1 | F4 test controls |
| Sound Framework | 0.1.3 | Plushie dependency |
| Pickup Hands | 0.1.1 | Plushie dependency |
| Hints Framework | 0.2.0 | Plushie dependency |
| Vehicle Framework | 0.2.1 | Courier dependency |
| Build Menu Framework | 0.2.2 | Power Poles dependency |

`../mod-bundle.json` records each included package's identity, version, SHA-256,
source repository and native entry hash. Runtime and asset bytes are retained;
embedded documentation contains player instructions and applicable credits.

The source builder verifies the inventory, package/file hashes, unchecked defaults,
dependencies, API/host requirements and game pins. Packages appear once under
`loader/packages/` in the built archives. All nine start unchecked. Existing user
versions and selections survive library seeding. These checks do not establish
loaded-world or multiplayer support for the combined selection.
