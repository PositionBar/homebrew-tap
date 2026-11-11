cask "positionbar" do
  version "0.2.0"
  sha256 "1accee66fef0b6cf22ae15093bc38c38ad3afc419eee4c9b0657493f6fcee552"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.2.0-1101/PositionBar-0.2.0-1101.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
