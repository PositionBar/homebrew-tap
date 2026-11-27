cask "positionbar" do
  version "0.7.3"
  sha256 "bdf8cf77a0b23c3f1acca84f21ebe566668ff9a0d2d5e2d48fbe316cdeee9fb8"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.7.3-1674/PositionBar-0.7.3-1674.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
