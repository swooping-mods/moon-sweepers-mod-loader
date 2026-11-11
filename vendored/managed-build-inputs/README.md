# Source-only BepInEx build input

`BepInEx-be791-host-and-compile-refs.zip` is an inert, deterministic selection
from the exact reviewed be.791 upstream archive. It is included only in source
distributions so CI and offline builds do not depend on a publisher endpoint
that returns HTTP 403 to hosted runners. Desktop distributions exclude this
entire directory and their package checks reject a leaked build input.

The 41 original host members and 172 managed compiler-reference images retain
their exact upstream paths and bytes. All 15 native CLR/JIT/debug/hosting and
runtime-configuration members under upstream `dotnet/` are excluded. The
managed images remain compiler metadata inputs, never an activated .NET 6 VM;
production packaging still replaces the entire platform directory with the
locked maintained CoreCLR 10 runtime. No reference rewriting or new runtime
dependency version is introduced by this selection.

`derivation.json` records the original and derived SHA-256 identities, every
retained/excluded member, and reference provenance. The 165 platform reference
images match exact members of Microsoft's MIT-licensed runtime pack 6.0.7;
its original license, third-party notices and package metadata accompany this
directory. The other seven references are the already documented MIT-licensed
6.0.0 application dependencies in `../managed-application-notices/`. Host
component rights and corresponding sources are retained by the ordinary
BepInEx notice inventory. This directory adds no project license.

Reproduce the selection with an independently obtained exact upstream ZIP:

```sh
python3 tools/derive_bepinex_input.py --source /path/to/BepInEx-Unity.IL2CPP-win-x64-be791.zip --output /path/to/derived.zip --manifest /path/to/selection.json
```

The manifest's `reference_provenance` and `notice_files` annotate the generated
selection with independently verified publisher correspondence and notices.
The lock's `local_path` is mandatory: missing or changed vendored bytes reject
staging instead of falling back to a different remote archive. `upstream_url`
and `upstream_sha256` identify provenance, while the locked staged filename and
digest identify the derived input actually consumed by the offline builder.
