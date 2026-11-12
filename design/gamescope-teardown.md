# Gamescope teardown qualification (I39)

I39 remains open. Retained evidence isolates a failing compositor teardown
observation from successful child-runner receipts and game shutdown observations.
It does not identify the crashing compositor code or establish an independently
observed native game exit. This design records the investigation boundary and
the gates needed for a defensible fix; it changes no launch behavior.

## Ownership and available source

The loader's [`plan()` and `_start_locked()`](../loader/moonloader/launch.py)
launch Steam's short `-applaunch` request in installed mode, or a native/private
Proton command in private mode. Neither path adds Gamescope. Installed Steam
owns the actual game process. Closing the loader leaves the user-started game
alone, as specified in [loader diagnostics](../specs/loader.md).

Gamescope is the outer compositor for automated qualification. Available source
in the sibling workshop (`moon-sweepers-modding/`) provides these boundaries:

| Source | Behavior relevant to teardown |
| --- | --- |
| `tools/private_session.py:runner_exit()` | Validates a fresh matching session/run/PID/start-time receipt; reports runner and compositor codes separately, and explicitly leaves native game exit unobserved. |
| `tools/private_session.py:main()` | Runs the owned Flatpak/Proton command synchronously and writes `runner-exit.json` before the primary Python child returns. |
| `tools/fast_game_cycle.py:_run()` | Starts Gamescope as a new process session around that child; `process.wait()` supplies its outer `exit_code`, and `normal_exit` currently means that code was zero. On timeout/interruption it signals only that owned process group. |
| `tests/test_private_session_exit.py` | Covers the separate exit observations, missing/stale/mismatching runner receipt rejection, and an independently unobserved native game exit. |

The workshop sources were inspected read-only. The observed SHA-256 values are
`fafbe736a77d4e513399d6d25a17900a5e1b5e919232eaa9ba72524ea2b686ab`
for `private_session.py` and
`d99eac46c588ed3e88ddc45479c3b1c87b7885e88446612e1d20871f696f3dfe`
for `fast_game_cycle.py`. The latter also matches the retained clock-probe run's
source inventory. These references identify inspected code, not a new dependency
or an integration into the public loader.

The loader's ignored `.local/steam-player-021/session.py` waits for its AppImage
child, writes `appimage-exit.json`, then holds the compositor's primary child
open until an `end-session` marker or a 1,200-second deadline. It intentionally
keeps the display alive for the test's Steam shutdown. That child is a session
keeper, not the game. Retained `.local/release-0.2.1/installed_repro.py` and
`installed_cycle.py` explicitly stop their owned Wine prefix before waiting for
Gamescope; their bootstrap-only cleanup is not normal game-quit proof.

No Gamescope compositor source or crash backtrace was found in this bounded
inspection of the loader, workshop launch helpers and named local Gamescope
checkout locations. No external source was acquired. The retained log identifies
Gamescope 3.17.0; that is a historical run identity, not a claim about the current
installed version.

## Retained observations

Evidence paths below are relative to the owning loader's normal checkout. They
remain ignored and read-only; profiles, game files and captures are not copied
into this design or the task worktree.

| Evidence | Observation and limit |
| --- | --- |
| `.local/steam-player-021/result.json` and `appimage-exit.json` | Actual installed Steam path: `normal_game_quit: true`, AppImage exit 0, Gamescope exit 139, `gamescope_teardown_passed: false`. Top-level `success: true` describes the recorded player-path scope; it does not clear the explicit teardown failure. |
| `.local/steam-player-021/gamescope.log` | Headless backend and RTX 2080 Ti selection; late `Unhandled libei event!`, then `Primary child shut down!` and an Xwayland broken pipe. The log has no crashing stack or independently attributed signal receipt. These lines alone do not prove libei caused the fault. |
| `.local/release-0.2.1/game-evidence/installed-b38b201b1659411b810a470da3c46241/result.json`, `world.exit_status` | Runner 0, compositor -11, teardown false, native game exit `not independently observed`. The top-level successful world qualification coexists with the failed compositor observation. |
| `.local/forward-compat/game/{result,runner-exit}.json`, run `fast-37d9da59c712476ba42d8e0e2e31a22d` | Startup/world pass and no listed runtime errors; runner 0; outer exit -11; `normal_exit: false` and `success: false`. The scenario passed while its complete harness gate remained failed. |

The existing [installed-deployment](../specs/public-deployment.md) and
[managed-runtime](../specs/managed-runtime.md) qualification caveats already
preserve this failure. The workshop's existing
`verification/2026-11-10-bepinex-adapter.md` records Unity shutdown followed by
runner 0 and compositor failure, including the actual Steam/AppImage path.
Those observations are consistent with a compositor teardown failure; they
do not locate a faulting function or rule out every harness ordering issue.

The -11 value is the Python-observed SIGSEGV form; the historical 139 report is
the shell-style representation associated with the same signal. Preserve each
raw code and its observer instead of silently translating every 139 into a
verified native signal. A bare exit status has no stack-level causal detail.

## Required behavior of a future change

Keep independent outcomes for the Steam request, child runner, observed game
shutdown, compositor teardown and cleanup/restoration. A runner exit 0 is only
runner completion. A compositor crash fails its teardown gate even when scenario
assertions pass. Missing game-process evidence stays unverified. In particular,
the fast-cycle `normal_exit` field must not be presented as an independently
observed game exit or used alone to classify a game crash.

Preserve original receipts and existing conservative aggregate failures. If the
workshop adds separate fields to fast-cycle results, retain the raw wrapper code
and require compositor success for any complete-run qualification claim. Do not
rewrite historical results to pass, suppress SIGSEGV, treat a forced stop as a
normal quit, or make the desktop loader manage unrelated Gamescope/Steam
processes to hide a qualification failure.

There is insufficient causal evidence for a production patch, a compositor flag
workaround or a shutdown delay. The first implementable change belongs to the
owning qualification harness once evidence identifies the failing boundary.
Any eventual compositor/dependency acquisition must follow external intake.

## Deferred verification gates

These gates require a later authorized runtime window; none is executed by this
static preparation work.

1. Record the exact Gamescope executable/version/digest, launch argv, backend,
   graphics driver and relevant dependency versions. Capture ordered milestones
   with observer identity: primary-child start/exit, child receipt publication,
   game shutdown evidence, compositor raw return code and owned cleanup signals.
   Keep private environments and profiles out of public diagnostics.
2. On the same hardware/backend, use one bounded, game-free owned primary child
   that writes a unique completion receipt and exits normally. Require its fresh
   receipt and separately record Gamescope exit. Repeat with the retained session
   keeper's explicit completion handshake. A clean first case and failing second
   case would narrow ordering; neither alone establishes game behavior.
3. If teardown still crashes, obtain a symbolized backtrace/core attribution for
   that exact owned compositor run, or equivalent reliable faulting-thread
   evidence. Compare shutdown ordering against the matching reviewed compositor
   source. Change one identified cause at a time; retain failed controls.
4. Verify any harness edit first with tiny pure-Python tests of separate exit
   classification, mismatching/missing receipt refusal, timeout/forced-stop
   labeling and cleanup ownership. Reuse `runner_exit()` rather than inventing
   weaker attribution. Run the game-free compositor cases after those checks.
5. Only after game-free teardown passes, replay the previously failing owned
   scenario with its exact selected inputs and isolation/preservation contract.
   Require scenario assertions, explicit shutdown evidence, fresh runner receipt,
   zero compositor exit and successful cleanup/restoration as separate gates.
   The actual Steam/AppImage path needs its own authorized replay to extend that
   claim; a private Proton replay does not substitute for it.

Record later results in the existing owning verification record and retained
receipts, with failures and skipped gates explicit. I39 can close only when the
previously failing teardown is reproduced, causally repaired and passes its
relevant runtime gates. This document completes source/preparation work only.
