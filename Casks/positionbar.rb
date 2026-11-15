cask "positionbar" do
  version "0.5.1"
  sha256 "3daa93b59ad05ded21dbc5a4bc46d90a678480f4263729f94d2c8fabe922ed33"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.5.1-1252/PositionBar-0.5.1-1252.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
