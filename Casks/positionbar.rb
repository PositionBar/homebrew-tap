cask "positionbar" do
  version "0.5.0"
  sha256 "96844d188dba6ea01f997e9fee7ae5e14790cf1dcd485e612db40eb511139a32"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.5.0-1235/PositionBar-0.5.0-1235.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
