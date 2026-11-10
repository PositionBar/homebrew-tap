from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import migrate_release_secrets as migration


class MigrationTests(unittest.TestCase):
    def test_only_the_four_signing_values_are_selected(self):
        env = {name: "fixture" for name in migration.SIGNING}
        env.update(GH_PAT="not-copied", TAP_WRITE_TOKEN="not-copied")
        self.assertEqual(set(migration.credentials(env)), set(migration.SIGNING))
        self.assertNotIn("not-copied", migration.credentials(env).values())

    def test_missing_signing_values_fail_before_encryption(self):
        with self.assertRaisesRegex(ValueError, "Missing existing signing credentials"):
            migration.credentials({})


if __name__ == "__main__": unittest.main()
