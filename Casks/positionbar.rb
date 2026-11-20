cask "positionbar" do
  version "0.6.1"
  sha256 "7b4cd1cfb9aea0cb11622446ef338236cf1df98082610f381f581c944c7c8d7a"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.6.1-1481/PositionBar-0.6.1-1481.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
