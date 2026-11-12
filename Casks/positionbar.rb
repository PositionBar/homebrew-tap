cask "positionbar" do
  version "0.3.1"
  sha256 "f4ea628107eabd4d5274c8a7bde412f04e2f89a809c65ac00bc36d60e70e8f1c"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.3.1-1126/PositionBar-0.3.1-1126.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
