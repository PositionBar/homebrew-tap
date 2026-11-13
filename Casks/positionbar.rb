cask "positionbar" do
  version "0.4.2"
  sha256 "8b6eef8ea5bdbe441729b0a489eeda0f499e883f53def90739869ad487c809ef"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.4.2-1156/PositionBar-0.4.2-1156.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
