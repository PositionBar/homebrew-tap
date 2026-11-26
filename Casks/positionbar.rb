cask "positionbar" do
  version "0.7.2"
  sha256 "53b2031bd8ca6a8b79a118f25a3690253b45c2abad0c7f42524e913b9d80000e"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.7.2-1666/PositionBar-0.7.2-1666.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
