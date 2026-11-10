# Package contract

`moon_mod_api.packages` is the executable authority for `moon-mod-package/v1`. The loader imports an exact snapshot of that implementation; it does not maintain a second validator.

A `.msmod` is a ZIP containing `manifest.json` and exactly the payload files named in its SHA-256 table. Required manifest fields are `schema`, `id`, `version`, `name`, `summary`, `description`, `author`, `kind`, `abi`, `entry`, `icon`, `requires`, `conflicts`, `claims`, `game` and `files`.

IDs are lowercase hyphenated names, at most 64 characters. Versions use `major.minor.patch` with an optional lowercase prerelease suffix. Icons contain PNG data with dimensions at most 1024 by 1024. Native entries use `MoonLab_ModStart/v1` through `/v7` and a DLL. Managed entries use `bepinex-il2cpp` with `BepInEx.IL2CPP/6-be791` and a root DLL. Companion tools use `PythonZipApp/v1`, a `.pyz`, and no game dependencies/conflicts/claims. The hook guide explains the required roles and marker for v5.

The archive and unpacked payload are limited to 64 MiB, 128 payload files and a 32 KiB manifest. Paths must have one portable spelling; absolute/traversal paths, Windows devices/streams, case collisions, symlinks, encryption and unlisted members fail. Integrity hashes do not authenticate an author or sandbox a native DLL.

`game.id` is `moon-sweepers`, `game.appid` is `5335510`, and `game.hashes` must contain one or more supported executable SHA-256 pins. The loader owns the currently supported game build; mod authors own their declared compatibility. A mod must not infer support merely because the game version string matches.

`resolve` requires explicit dependency selection and yields deterministic dependency-first order across native/managed game mods. It rejects missing dependencies, cycles, declared conflicts, exclusive hook overlap, duplicate input/physics owners and multiple camera overrides. The capacity is 64 selected game mods; capacity does not imply combined gameplay qualification.

The extraction retains the existing package schema and `MoonLab_*` exported symbols. API package version 0.6.0, C hook ABI 1, native package ABIs v6/v7 and the mod's own version are separate version domains.

Optional `build_items` entries declare each saved building `kind` and stable
namespaced `key`. They require the native `build-menu-framework` dependency.
Only that framework may declare `build_menu_max_kind`; current release 0.2.0
declares 384. Historical framework manifests without this capability default
to 224. The resolver rejects overlapping declared building kinds and providers
that exceed the selected framework's capability before launch. Legacy providers
without declarations still need runtime conflict checks. See [building API](building-api.md).

Managed mods declare `bepinex: {guid: "author.plugin", data_root: "UniqueNamespace"}`.
Plugin GUIDs and data namespaces are unique case-insensitively in a selected set;
host/core/config/cache namespaces are reserved. Managed packages use exclusive
hook claims for their real targets, not native shared-role markers. Optional
`mode: external` metadata records `external: {adapter, repository, revision}`
for a supplied managed plugin. It is provenance and deployment identity, not an
instruction to download or run anything. Ordinary authored managed plugins need
no external-mode designation.

The offline SDK understands package backends without promising that a given
loader hosts all of them. Loaders pass `available_runtimes` to `resolve` when
checking their actual host. A matching native/managed graph does not prove
cross-runtime startup ordering or framework callability; hosting must qualify
those separately. [Mod-provided interfaces](interfaces.md) adds owner-qualified
API/ABI/size/limit requirements and the optional generalized `build_api` route.
Native v6 requires `runtime_api_abi: 1`. Shared hook roles in v6 still require
hook framework ABI 1; a registry-only v6 package need not claim a shared hook.
Target loaders pass their actual `runtime_api_abi` (zero when absent) as well as
backend availability. Metadata validation alone never grants runtime support.

Managed packages opting into native `requires_apis` also declare
`runtime_api_abi: 1`. Their target must advertise `runtime_readiness_abi: 1`.
This consumer-only bridge preserves native provider ownership; managed packages
cannot declare native `provides`. See [managed services](managed-services.md).

Native v7 adds mandatory host-adapter admission without changing the C startup
function or runtime table. It requires `runtime_api_abi: 1` and a nonempty
`requires_host` map, for example `{"interaction": 1}`. Keys match
`[a-z][a-z0-9_]{0,63}`; at most 32 exact positive uint32 ABI requirements are
allowed. This metadata is unavailable to earlier native/managed/companion
packages; older loaders reject the new package ABI instead of ignoring a
mandatory requirement. Native v7 retains v6 publication and shared-hook rules.

Target loaders pass their runtime receipt's `host_capabilities` map to `resolve`
and `require_available`, both during selection and again before preparation.
Missing or null receipt maps must become `{}`: an explicit empty target refuses
any required adapter. The SDK's default `host_capabilities=None` permits offline
inspection only. Extra available capabilities are harmless; missing, malformed
or different ABI values reject. Capability names describe loader adapters;
ordinary framework APIs still use owner-qualified `requires_apis` and package
dependencies. No framework owner identity is registered in this host map.
