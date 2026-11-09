# PositionBar Homebrew tap

Homebrew Casks for [PositionBar](https://positionbar.com).

## Status

This repository is being prepared for a future Homebrew distribution channel. No installable cask is published yet.

The first cask needs a published PositionBar release, its download URL, and the SHA-256 of that exact artifact. Development builds and the website's test update feed are not distribution artifacts.

## Installation

After the first cask is published:

```sh
brew tap positionbar/tap
brew install --cask positionbar
```

These commands will not install PositionBar until `Casks/positionbar.rb` is available.

## Add the first cask

1. Use an approved public release signed with Developer ID and notarized for distribution.
2. Add `Casks/positionbar.rb` with its version, verified download URL, exact SHA-256, supported architecture, minimum macOS version, and `app "PositionBar.app"`. Read these values from the release artifact rather than development defaults.
3. Run `brew style --cask positionbar/tap/positionbar` and `brew audit --cask --online positionbar/tap/positionbar`, then verify installation and uninstall behavior on a supported Mac.
4. Update this README with the verified installation instructions when the cask is available.

See [Homebrew's Cask Cookbook](https://docs.brew.sh/Cask-Cookbook) for the cask format.
