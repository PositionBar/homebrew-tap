cask "positionbar" do
  version "0.1.2,1085"
  sha256 "026043ae4558eaf735bbc06af649f3ba635d35be3186c57fced6154a57155a2e"

  url "https://github.com/PositionBar/releases/releases/download/positionbar-0.1.2-1085/PositionBar-0.1.2-1085.dmg"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  auto_updates true
  depends_on macos: :tahoe

  app "PositionBar.app"
end
