# PositionBar Homebrew tap

Public release assets and casks for [PositionBar](https://positionbar.com/).
No installable cask is implied until a real paired release has passed the checks below.

## Unified Actions release

The `Paired PositionBar release` workflow checks out a fixed commit from private
`sorcererxw/positionbar`. Both channels share that source SHA, marketing version,
build and global Build ID. TestFlight uses the App Store target without Sparkle;
Homebrew uses a separately signed, notarized Developer ID app with Sparkle.
The cask and signed appcast reference the exact same notarized ZIP bytes.

Publication uses only manual `workflow_dispatch`. `mode=verify` is the default and runs
offline regressions plus both unsigned archives on the standard GitHub-hosted
`xcode-27` arm64 runner. It does not allocate a global number, sign, notarize,
upload TestFlight, create a Release or change the cask. The requested source
commit must already include the paired-release implementation.

For this repository's own PRs, `Tap checks` also verifies fixed reviewed source
`37bba86e741df5d16de36ea775e1d3aa99b817c7` on `xcode-27`. It runs the actual
Updater suite and both unsigned archives using only the source-read token. Fork
PRs never receive private source. This PR verification cannot sign or publish and
does not require merging the new manual workflow into main first. The reference
SHA is an integration-test input, not a publication version fallback.

`mode=release` is an actual publication. It runs only from tap main after
verification, with a full `source_sha` matching the observed source main for a
fresh release. It uploads TestFlight once, saves its accepted checkpoint, then
builds/signs/notarizes Homebrew, publicly verifies ZIP/feed/notes and updates tap
main. Upload acceptance does not mean Apple processing or external beta review
is complete. Do not run a local publisher and Actions publisher concurrently.

## Configuration contract

Repository Secrets, already prepared separately:

- `GH_PAT`: read access to the private source repository.
- `APP_STORE_CERTIFICATES_P12_BASE64`, `APP_STORE_CERTIFICATES_PASSWORD`.
- `APP_STORE_PROFILE_BASE64`, `APP_STORE_API_PRIVATE_KEY`.
- `DEVELOPER_ID_CERTIFICATE_P12_BASE64`, `DEVELOPER_ID_CERTIFICATE_PASSWORD`.
- `SPARKLE_PRIVATE_KEY`: the existing key matching the reviewed source catalog public key.

Repository Variables:

- `APP_STORE_API_KEY_ID`.
- `APP_STORE_API_ISSUER_ID`.

Tap writes use the workflow's short-lived `GITHUB_TOKEN`, not the source-read
PAT. No extra persistent credential is generated. Temporary signing keychains
are removed and search lists restored. Secrets are scoped to signing steps and
stripped from compiler children. No credential, private source, build log,
TestFlight pkg or dSYM is included in recovery artifacts. Configuration names
existing in Settings do not prove signing, ASC, notarization or PAT functionality.

The app embeds this stable signed feed URL:
`https://github.com/PositionBar/homebrew-tap/releases/latest/download/appcast.xml`.
New Release assets are publicly read back before that release becomes latest.
An older retry cannot replace a newer latest build. The cask declares
`auto_updates true` and retains signed Sparkle update checks.

## Recover without a second TestFlight upload

Dispatch `mode=release` again with the original `source_sha` and `resume_run_id`.
The workflow verifies the original run belongs to tap main and this workflow,
then restores `homebrew-state` or `testflight-state`. Both are retained for 30
days. A source main advance does not change the restored release identity.

An accepted TestFlight receipt and original build snapshot are mandatory.
Uncertain/unaccepted uploads stop for App Store Connect reconciliation; they
are never treated as accepted. The job's ordinary Re-run button without a
checkpoint stops before another allocation/upload.

Homebrew reuses and reverifies the exact retained ZIP, or downloads its original
public URL and checks the saved SHA-256/length. If the exact unpublished bytes
are missing, it stops rather than rebuilding a replacement under the same
version. Immutable uploaded assets and release records cannot be substituted.
A lost upload/push response is reconciled before retry, without force-push.

## Cask verification and offline tests

```sh
python3 -B scripts/cask.py check --receipt /absolute/path/to/homebrew.json
python3 -B scripts/cask.py publish --receipt /absolute/path/to/homebrew.json
python3 -B -m unittest discover -s tests -v
```

`publish` is dry-run unless `--execute` is supplied. Execution downloads the
exact public ZIP, verifies identity, architecture, Developer ID, notarization,
Gatekeeper, entitlements and Sparkle feed/key, styles the cask, then commits only
`Casks/positionbar.rb` and its immutable `Releases/positionbar-<version>-<build>.json`
record. It verifies remote main after push and can reuse its own interrupted
local candidate/commit. Machine-readable results use `--result`; logs stay on
stderr.

Offline tests mock Apple and public network boundaries. Passing them, YAML/bash
syntax validation, or unsigned archives does not establish hosted signing,
notarization, upload acceptance, a public Release, `brew audit`/`brew install`, or
cross-machine update behavior. Those remain separate operational acceptance.
