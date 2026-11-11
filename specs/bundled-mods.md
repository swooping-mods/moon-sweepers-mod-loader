# Starter mod bundle

Squishy Plushie, Futuristic Courier, Power Poles, F4 Debug Menu and five required
frameworks are included as pinned distribution packages. `vendored/mod-bundle.json`
records versions, hashes, public source repositories and native entry hashes.

The nine prebuilt distribution inputs are deliberately vendored under
`vendored/mod-bundle/packages/`. Gameplay source and asset authoring remain in
their owning projects. No build resolves dependencies or downloads mods.
`tools/mod_bundle.py` rejects missing, additional, changed, duplicate or aliased
inputs and mismatched manifest identity/version/defaults. It verifies the entire
selection against the loader's game pins and runtime capabilities, including
provider interfaces, build-menu limits, dependencies and hook claims.

`tools/build.py` maps the verified bytes to `loader/packages/` in its source ZIP,
without duplicating the vendored package inputs. Its existing source seal and
build receipt include package identities. Builds from this source ZIP use the
same runnable layout as their input. Windows and Linux builders retain packages,
the bundle lock and public notices; platform checkers verify the exact locked package
set inside their materialized archives. Windows archive bytes must also match
the materialized inputs. The common GUI smoke check asserts the nine imported
mods and unchecked defaults using temporary data, without starting a game.

`Service.seed()` uses `loader/packages/`, falling back to the vendored inputs in
the development checkout. First-time imports populate the library with all nine
unchecked. Existing active versions and checked/unchecked choices remain intact.
Users select the desired mod and its declared dependencies or use Select all;
dependency validation continues to reject incomplete selections. No game is
prepared or started automatically. Other local `.msmod` imports remain supported.

`tests/test_mod_bundle.py` exercises real package import, full dependency ordering,
missing-dependency rejection, reseeding with an existing user version/selection,
tampered/missing/extra inputs and source layout. The normal full host check runs
the bundle verifier before tests. Feature gameplay evidence remains per package;
these checks do not qualify the exact nine-mod combination in a loaded world,
native Windows gameplay, save/reload or real co-op.
