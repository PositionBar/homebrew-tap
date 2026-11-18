cask "positionbar" do
  version "0.6.0"
  sha256 "b7614c9afbb05d40d3d072e5f92f6d3042d360ee33dcc5c62a2b383c4b430d23"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.6.0-1394/PositionBar-0.6.0-1394.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
