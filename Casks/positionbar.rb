cask "positionbar" do
  version "0.1.3,1095"
  sha256 "c8300cf55e2404902997cd43439a84d81d0cfec95746833738232cc256219da4"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.1.3-1095/PositionBar-0.1.3-1095.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
