# PositionBar Homebrew tap

Public automation and release assets for PositionBar's notarized direct distribution.
An installable cask exists only after a real signed release has passed verification.
TestFlight is not part of the current publication path.

```sh
brew install --cask positionbar/tap/positionbar
```

The website links to this repository's [Releases](https://github.com/PositionBar/homebrew-tap/releases).
The same immutable DMG is used by downloads, Sparkle and the cask.

## Workflow

`PositionBar direct release` (`.github/workflows/release.yml`) runs on GitHub-hosted
`xcode-27` runners, with offline tap tests on Ubuntu. This single workflow handles
automatic checks and manual publication. Pushes and pull requests never publish.

- `source_sha`: optional expected application commit from the private `sorcererxw/positionbar` repository; defaults to its current main. Recovery requires the original full SHA.
- `mode`: `verify` by default; `release` explicitly signs, notarizes and publishes.
- `resume_run_id`: optional earlier direct-release run from this tap's main workflow.

Fresh publication requires both this workflow and application source to be on main.
Manual or API callers select `mode=release`; no source SHA is needed for a fresh
release. The workflow resolves main once, pins that exact commit through the jobs,
and checks it again before publication. Default `mode=verify` only checks it.
Verification checks the pinned source, locked dependencies, offline regressions,
executed Updater XCTest cases and one unsigned Universal direct-distribution archive. It
allocates no global Build ID and uses no signing or publication credentials.
The PR check pins the exact reviewed source as `PR_SOURCE_SHA` in `release.yml`; update that SHA
alongside source changes before treating cloud verification as current evidence.

Actual release reserves a new global Build ID with variant `developer-id-release`,
keeps Team `TX6HZR5RB7` / Bundle ID `com.positionbar.app`, signs with Developer ID
Application and hardened runtime. The App targets macOS 26+ and must contain both arm64 and x86_64. It notarizes/staples the App, creates an APFS/LZFSE DMG with an Applications link, signs/notarizes/staples the DMG, then verifies both layers with Gatekeeper and a read-only, no-auto-open mount.
The receipt fixes source, version, Build ID, DMG SHA-256/length, architectures,
entitlements, Apple identity and Sparkle feed/key. No TestFlight receipt is required.
The cask publisher downloads the public bytes and verifies those facts again.

Sparkle's signed canonical feed is:
`https://github.com/PositionBar/homebrew-tap/releases/latest/download/appcast.xml`.
Assets are immutable; missing assets can be added, existing bytes cannot change.
Latest promotion and cask updates refuse to roll back a newer Build ID.

## Existing repository credentials

| Input | Purpose |
| --- | --- |
| Secret `GH_PAT` | Read the fixed private source; checkout does not retain it |
| Secret `DEVELOPER_ID_CERTIFICATE_P12_BASE64` | Existing Developer ID certificate and private key on an ephemeral signing keychain |
| Secret `DEVELOPER_ID_CERTIFICATE_PASSWORD` | Unlock that P12 |
| Secret `APP_STORE_API_PRIVATE_KEY` | Existing Apple API P8, used by notarytool |
| Variables `APP_STORE_API_KEY_ID`, `APP_STORE_API_ISSUER_ID` | Identify that notarization API key |
| Secret `SPARKLE_PRIVATE_KEY` | Sign the DMG, appcast and release notes with the existing key |
| Automatic `github.token` | Public release assets, retained artifacts and cask push |

App Store application/installer certificates and provisioning profiles are not
read by this workflow. Existing stored credentials need not be deleted. Secret
presence does not prove signing, notarization or push permissions work. The local
TestFlight scheduler must be stopped before enabling this workflow as the writer.

## Recovery

`release-state` saves identity before signing. `homebrew-state` saves only the
identity, non-secret receipt, exact notarized DMG and signed appcast/notes for 30
days. No private source, signing material, Keychain, intermediate archive, dSYM,
package cache or build log is uploaded to this public repository.

Dispatch again with the original source SHA and `resume_run_id`. Recovery accepts
only this tap's main direct-release workflow. A checkpoint without a verified DMG
cannot continue compiling: start a new attempt and get a new Build ID. Once DMG
facts are saved, restore the exact bytes or retrieve the original URL; never
rebuild a replacement under the old identity. A job rerun with missing state
fails closed. Legacy TestFlight checkpoints are not accepted.

`python3 -B scripts/cask.py publish --receipt /absolute/homebrew.json` is a dry run.
`--execute` explicitly verifies the download and writes/pushes the cask plus its
immutable release record. Git responses are read back; retries preserve their own
staged candidate or local commit, never force-push.

```sh
python3 -B -m unittest discover -s tests -v
```

These tests are offline and use synthetic repositories. Their success does not
prove Apple notarization, public availability, installation or native interaction.
