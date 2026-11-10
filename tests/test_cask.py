import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cask


class RenderingTests(unittest.TestCase):
    def test_universal_cask_has_no_arch_restriction(self):
        value = {"version": "0.1.0", "build": 1015, "artifact": {
            "sha256": "b" * 64, "appName": "PositionBar.app",
            "url": "https://github.com/PositionBar/releases/releases/download/positionbar-0.1.0-1015/PositionBar-0.1.0-1015.dmg"}}
        contents = cask.render_cask(value, "tahoe")
        self.assertIn('  version "0.1.0,1015"\n', contents)
        self.assertIn("  depends_on macos: :tahoe\n", contents)
        self.assertNotIn("depends_on arch:", contents)
        self.assertIn("  auto_updates true\n", contents)


if __name__ == "__main__": unittest.main()
