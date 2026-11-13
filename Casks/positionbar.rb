cask "positionbar" do
  version "0.4.1"
  sha256 "c6126a499902918293d3fe76a26d729332722c000c983bd6a4ffd726f3d27abc"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.4.1-1155/PositionBar-0.4.1-1155.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
