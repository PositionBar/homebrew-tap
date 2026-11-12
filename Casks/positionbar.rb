cask "positionbar" do
  version "0.3.0"
  sha256 "a159d3d730ac67901d41b3a7507b21c5858424924be7dd109aa052a011e1c6d0"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.3.0-1122/PositionBar-0.3.0-1122.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
