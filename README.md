# PositionBar Homebrew tap

Homebrew Casks for [PositionBar](https://positionbar.com/).

## Publication model

This repository is the public Release and cask target for PositionBar's local
release pipeline. Each accepted TestFlight build is paired with a separately
built Developer ID ZIP from the same source SHA, marketing version, build, and
Build ID. The ZIP is notarized, stapled, checked with Gatekeeper, and published
under `PositionBar/homebrew-tap`, not the PositionBar source repository.

The cask app does not embed Sparkle, an App Store profile, or in-app update
configuration. A cask is eligible only after the matching TestFlight upload has
the status `upload_accepted_processing_pending`.

The source pipeline writes a `homebrew.json` receipt containing the accepted
TestFlight facts, exact artifact SHA-256 and length, notarization results, and
public GitHub Release URL. Do not hand-edit or substitute that receipt: the tap
uses it to reject mismatched source revisions, versions, builds, Build IDs,
artifact bytes, architectures, entitlements, or download URLs.

There is no `prepared.json` stage and no source release-catalog gate. This tap
does not build, sign, notarize, upload TestFlight, or rebuild the App.

## Check

Review the public artifact and rendered cask facts without changing the tap:

```sh
python3 -B scripts/cask.py check \
  --receipt /absolute/path/to/homebrew/homebrew.json \
  --result /absolute/path/to/cask-result.json
```

`check` downloads the exact public Release asset, verifies SHA-256 and length,
then checks the extracted App's version, build, source revision, Build ID,
architectures, Developer ID signature, notarization, Gatekeeper result, and
entitlements. It reports a candidate only; it does not write, commit, or push.

## Publish

`publish` is a dry-run unless `--execute` is present:

```sh
python3 -B scripts/cask.py publish \
  --receipt /absolute/path/to/homebrew/homebrew.json
```

After reviewing the dry-run:

```sh
python3 -B scripts/cask.py publish \
  --receipt /absolute/path/to/homebrew/homebrew.json \
  --execute \
  --result /absolute/path/to/cask-result.json
```

The executing command re-downloads and verifies the exact artifact, renders
`Casks/positionbar.rb`, writes the immutable pairing record
`Releases/positionbar-<version>-<build>.json`, runs `brew style --cask`, and
commits only those two files. It pushes tap `main` and verifies that the remote
tip equals the local commit.

Machine-readable JSON goes to stdout and, when requested, `--result`; command
logs go to stderr. The source pipeline uses this result file instead of parsing
mixed output.

`already published` means the generated cask and record already match local and
remote `main`. If commit or push is interrupted after the local commit exists,
rerunning the same `--execute` command verifies and reuses that exact commit
without creating a duplicate. A push or remote read-back failure is reported as
uncertain and must be checked against tap `main`; do not force-push.

Homebrew requires an installed and explicitly trusted tap before `brew audit`
will load a cask by name. This repository does not change Homebrew trust or
security settings. After an authorized publication, an online audit can be run
separately:

```sh
brew audit --cask --online positionbar/tap/positionbar
```

## Offline tests

```sh
python3 -B -m unittest discover -s tests -p 'test_cask.py' -v
```

The tests use a synthetic universal App bundle, a temporary tap Git remote, and
mocked Apple/GitHub verification boundaries. They cover TestFlight pairing,
artifact download and signature validation, cask rendering and immutability,
release-record identity, dry-run behavior, commit/push recovery, and separation
of machine output from command logs.

These are offline checks. They do not prove that a real Developer ID build,
notarization, public Release download, tap push, `brew style`, `brew audit`, or
`brew install` succeeded. Real acceptance requires a new paired release round.

There is intentionally no GitHub Actions workflow. Publication runs from the
local Mac with existing credentials and explicit execution.
