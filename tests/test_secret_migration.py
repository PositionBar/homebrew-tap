import hashlib
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import migrate_release_secrets as migration


class MigrationTests(unittest.TestCase):
    def test_only_healthy_unexposed_tokens_are_migrated_with_signing_values(self):
        env = {name: "fixture" for name in migration.SIGNING}
        env.update(LEGACY_GH_PAT="test-token", BLOCKED_TOKEN_SHA256="blocked")
        def healthy(path, token):
            return {"sha": "a" * 40} if path.endswith("/commits/main") else {"permissions": {"push": True}}
        self.assertEqual(len(migration.credentials(env, healthy)), 6)
        self.assertEqual(set(migration.credentials(env, lambda *args: None)), set(migration.SIGNING))
        env["BLOCKED_TOKEN_SHA256"] = hashlib.sha256(env["LEGACY_GH_PAT"].encode()).hexdigest()
        def forbidden(*args): raise AssertionError("Exposed token must not be used")
        self.assertEqual(set(migration.credentials(env, forbidden)), set(migration.SIGNING))

    def test_missing_signing_values_fail_before_encryption(self):
        with self.assertRaisesRegex(ValueError, "Missing existing signing credentials"):
            migration.credentials({})


if __name__ == "__main__": unittest.main()
