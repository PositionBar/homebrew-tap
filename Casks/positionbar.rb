cask "positionbar" do
  version "0.8.0"
  sha256 "e0df1d3a68d95f6587c2440d52e98d1c8d6778005d55a9874c72853c158993f4"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.8.0-1711/PositionBar-0.8.0-1711.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
