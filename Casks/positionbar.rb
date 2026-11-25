cask "positionbar" do
  version "0.7.1"
  sha256 "36cbc111214b686705c7560fe7d7dcd9a3a0ed13bd4e5530c56e2ee6693c7e88"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.7.1-1640/PositionBar-0.7.1-1640.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
