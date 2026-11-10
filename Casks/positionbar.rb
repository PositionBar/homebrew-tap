cask "positionbar" do
  version "0.1.1,1073"
  sha256 "e359c872e05f9b6eace82ea5f2f4a2d4f3b0b315c5c7822dc53181f16af5b83b"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.1.1-1073/PositionBar-0.1.1-1073.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
