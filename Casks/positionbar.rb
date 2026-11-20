cask "positionbar" do
  version "0.6.2"
  sha256 "4a2c330046c6943c41fc4d87ca527907516658cc758750e17465bcbd3a255f7d"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.6.2-1528/PositionBar-0.6.2-1528.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
