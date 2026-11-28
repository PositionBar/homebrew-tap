cask "positionbar" do
  version "0.8.1"
  sha256 "4417fc37d6a2a55afae10d4fdfa79c69b2ee62311782a3f5b195e748ecfa3080"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.8.1-1714/PositionBar-0.8.1-1714.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
