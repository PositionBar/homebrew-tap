cask "positionbar" do
  version "0.6.4"
  sha256 "4649be3425c5c989ead725c50217b326a236c59b10029b3303d3382e40f744d8"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.6.4-1574/PositionBar-0.6.4-1574.dmg"
  name "PositionBar"
  desc "Portfolio tracker for the macOS menu bar"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
