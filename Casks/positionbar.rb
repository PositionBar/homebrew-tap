cask "positionbar" do
  version "0.6.3"
  sha256 "fac34cd617722f86b888d1d26c7dff625db7c5a64def985f96666d7535b493c4"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.6.3-1565/PositionBar-0.6.3-1565.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
