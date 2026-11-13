cask "positionbar" do
  version "0.4.0"
  sha256 "5473e7e423578310e4b96daf020e9044cccc6bb44a9563cc7433d41ae85f32fe"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.4.0-1154/PositionBar-0.4.0-1154.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
