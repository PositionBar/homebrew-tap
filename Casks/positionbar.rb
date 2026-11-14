cask "positionbar" do
  version "0.4.3"
  sha256 "b3c3c4f61ece2352843bf152ea0023ca7b3a0bf814a4ac8395d6d362d785051d"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.4.3-1200/PositionBar-0.4.3-1200.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
