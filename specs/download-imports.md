# Adding downloaded mods

The desktop offers **Add mods…** (multi-file picker), **Add folder…**, and local
file/folder drag-and-drop onto the window or mod list in Grid, Details and Text
views. The header and empty state explain drops. File operations run in the
existing worker; imports/drops are unavailable during another operation or a
loader-owned game process. Pickers can be cancelled without changing state.

`loader/moonloader/downloads.py`, `Service.import_downloads()` and the UI share one
import path. The CLI's existing `--install PATH` also accepts these inputs:

- `.msmod` archives, including several in a selected folder or ZIP download;
- unpacked packages with the standard `manifest.json`, optionally nested under
  a release wrapper directory;
- the complete reviewed MarsSweepers 0.6.1 folder/ZIP in its upstream
  `BepInEx/plugins/MarsMod/` and `BepInEx/MarsMod/voice/` layout.

Unpacked packages retain their advertised checksums. Only manifest-listed files
are repacked; adjacent scripts, runtime installers and unrelated files are not
copied or executed. Plain ZIPs are inspected through bounded reads, without
extracting their paths. Links/reparse points, devices, encryption, unsafe paths,
case collisions and oversized inputs reject. Limits are 32 input/package
candidates per operation, 2,048 entries, eight nested path components, 256 MiB
expanded input and the API's existing 64 MiB per-package limit. Loose DLLs and
unknown third-party layouts produce guidance instead of guessed native ABIs,
game pins or hook claims. No network, compiler, installer or plugin runs.

Successful imports use the existing immutable library and remain unchecked;
existing checkmarks survive updates. Repeated identical candidates are deduped.
Different versions of one ID in a batch report an error rather than silently
overwriting the first. Results list successful imports and per-input errors;
valid inputs survive a failure elsewhere in the batch. A malformed candidate
can stop further discovery within that selected folder/ZIP; select the valid
package directly or fix that download. Existing library data remains intact.

`vendored/import-profiles/` owns pinned recognition templates and first-party
support assets. `marssweepers.json` derives from the owning external integration's
existing wrapper. All eight user-supplied DLL/voice hashes must match the reviewed
candidate. The unchanged external-mode metadata, backend, game pins, namespace
and hook claims are retained; an original compatibility companion is included.
No upstream Mars DLL, voices, source or BepInEx runtime is distributed. The source
builder and imports verify support asset hashes. Updates require an intake and
the owning integration's new exact-byte qualification, not inferred compatibility.

Mars import does not attach its host or change deployment mode. The UI reports
the need for the supported BepInEx runtime and **Private game copy**. Installed
mode and native-only releases still reject managed preparation. Package import
does not qualify new runtime/game/Unity builds or co-op. Existing managed host
and deployment behavior is described in [managed runtime](managed-runtime.md).

The UI's readiness check passes the runtime receipt's readiness and host
capabilities alongside its API ABI, matching service preparation. This admits
supported v7 imports such as the plushie and keeps missing-host failures visible.

`tests/test_downloads.py` covers source forms, profiles, unchanged checksums,
partial success, selected-state preservation, version ambiguity, unsafe paths,
links, budgets and packaged profile integrity. The existing Qt interaction gate
also exercises both pickers, list-viewport drops and busy-state refusal.
`tools/check_mod_import_ui.py` runs those flows and captures wide/narrow, empty,
success and error states in private headless Gamescope without a game launch.
