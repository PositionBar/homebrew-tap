# PositionBar Homebrew tap

Homebrew Casks for [PositionBar](https://positionbar.com/).

## Status

No installable cask is published yet. The local pipeline consumes a release
stage produced by PositionBar's existing `scripts/release.py prepare`; it does
not build, sign, notarize, or upload the App.

The main App catalog currently has no published release, so any generated cask
is a test candidate and must not be committed as a public release.

## Requirements

- macOS with the installed Homebrew used for cask checks.
- A PositionBar source checkout containing the release contract:
  `scripts/release.py`, `scripts/releases.py`, `scripts/verify-signature.swift`,
  the release catalog, and the publishing example with the Team ID.
- A release stage created by `scripts/release.py prepare`, containing
  `prepared.json`, the exact ZIP, release notes, and signed `appcast.xml`.

The tap pipeline imports the source repository's existing `verify_feed`,
`verify_bytes`, `verify_notes`, `verify_appcast`, and `verify_app` functions.
It does not maintain a second signature or notarization implementation.

## Local flow

Use the same source checkout and stage for all three commands:

```sh
SOURCE=/absolute/path/to/positionbar
STAGE=/absolute/path/to/positionbar-release-stage

python3 -B scripts/cask.py check \
  --positionbar-repo "$SOURCE" \
  --prepared "$STAGE/prepared.json"
```

`check` validates the staged bytes, Sparkle signatures, Developer ID
signature, notarization ticket, Gatekeeper result, App version, App bundle,
architectures, and minimum macOS version. It derives version, URL, SHA-256,
bundle name, architecture, and minimum macOS from the release contract and
artifact. It does not write or publish anything.

Generate a reviewable candidate:

```sh
python3 -B scripts/cask.py generate \
  --positionbar-repo "$SOURCE" \
  --prepared "$STAGE/prepared.json" \
  --output Casks/positionbar.rb
```

Generation is idempotent and rejects downgrades. Metadata and DSL corrections
are allowed for an existing version, but its artifact URL and SHA-256 cannot
change. The output says `candidate written; not published`.

## Publish to this tap

The App release must first complete through `scripts/release.py publish`, and
the source catalog must contain the exact build with `status: "published"`.
`prepared.json` alone is never treated as publication evidence.

Publish is a dry-run unless `--execute` is present:

```sh
python3 -B scripts/cask.py publish \
  --positionbar-repo "$SOURCE" \
  --prepared "$STAGE/prepared.json"
```

After reviewing the dry-run:

```sh
python3 -B scripts/cask.py publish \
  --positionbar-repo "$SOURCE" \
  --prepared "$STAGE/prepared.json" \
  --execute
```

The executing command:

1. Re-runs all local artifact and source-contract verification.
2. Requires the source catalog to mark the exact release `published`.
3. Downloads the public ZIP without following redirects and compares SHA-256.
4. Runs `brew style --cask`.
5. Commits only `Casks/positionbar.rb`, pushes tap `main`, and verifies the
   remote commit.

`already published` is returned only when local and remote tap `main` already
contain the generated cask. If a push fails after its local commit, the command
reports an uncertain publication state; rerunning the same command reuses that
commit and retries the push without creating a duplicate.

Homebrew requires an installed and explicitly trusted tap before `brew audit`
will load a cask by name. This pipeline does not change Homebrew trust settings.
After an authorized publication, run the online audit separately if desired:

```sh
brew audit --cask --online positionbar/tap/positionbar
```

## Offline tests

```sh
python3 -B -m unittest discover -s tests -v
```

Tests use a synthetic universal App bundle and a local bare Git remote. They
mock the source repository's cryptographic and Apple verification calls because
the fixture is not Developer ID signed or notarized. The tests cover missing or
tampered staging, minimum-version mismatch, valid cask generation, idempotent
updates, downgrade rejection, catalog publication gating, public checksum
failure, normal generate-then-publish, repeated publish, and recovery after a
failed push. They do not prove a real release is signed, notarized, published,
installable, or accepted by Gatekeeper.

There is intentionally no GitHub Actions workflow. Publication is run from the
local Mac with existing credentials and explicit execution.
