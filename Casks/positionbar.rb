cask "positionbar" do
  version "0.2.1"
  sha256 "939bf9ce8dc158a5cbd1e748c4ebd0b58af41e4f75de6f5e557dbd62240300ed"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.2.1-1117/PositionBar-0.2.1-1117.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
