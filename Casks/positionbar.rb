cask "positionbar" do
  version "0.7.0"
  sha256 "b012457e5f90df6fe78224cce48733477e5d8c529dae2117b36be384950d5feb"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.7.0-1606/PositionBar-0.7.0-1606.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
