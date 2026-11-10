# Building independent native mods

The organization keeps three roles: this API defines shared contracts and
package tools, Moon Sweepers Mod Loader hosts those contracts and owns the
game-specific adapter, and each framework/gameplay mod owns its implementation,
domain SDK, assets and releases. The mod index links to available projects.

The loader's source checkout/distribution includes `sdk/native/`, with the
checked `runtime/native/` and `runtime/sdk/` header layout for Steam IL2CPP
1.0.5. Copy a reviewed snapshot into an author's source export when those game
bindings are required. Existing relative includes remain usable without the
original workshop. The adapter is game-build specific; its presence grants no
compatibility with another executable build.

Framework SDKs remain in each framework's source repository. A consumer includes
the public headers and declares the matching package/API dependencies. Including
a header does not install or initialize a provider. Core runtime contracts stay
content-pinned to this API; the loader checks its adapter's copied core headers
against that pin.

The maintainer's independent mod exports provide `build.py --check` for source
identity and `build.py` for an offline build under `.local/build/`. Native
compilation uses installed Clang, lld-link and llvm-dlltool; companion packaging
uses Python. No workshop checkout, game files or automatic tool installation is
required. Exact qualified packages and newly compiled candidates have distinct
evidence: rebuilt bytes require their own gameplay checks.

Players install the loader and mod packages. They do not separately install this
developer SDK or the workshop. GitHub hosts source and loader releases; each mod
author chooses their distribution destination, including Nexus.
