cask "positionbar" do
  version "0.1.4"
  sha256 "3914693dc0fdfb0baa419f20d362dd8a08b6a0ed120d31cc5695642efc76a80e"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.1.4-1097/PositionBar-0.1.4-1097.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
