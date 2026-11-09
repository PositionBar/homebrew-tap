import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci

class InputTests(unittest.TestCase):
    def test_source_requires_full_sha_and_current_main_only_for_fresh_release(self):
        with patch.object(ci, "github", return_value={"sha": "a" * 40}) as github:
            self.assertEqual(ci.resolve_source("b" * 40, False), "b" * 40)
            github.assert_not_called()
            self.assertEqual(ci.resolve_source("a" * 40, True), "a" * 40)
            with self.assertRaisesRegex(ValueError, "main SHA"):
                ci.resolve_source("b" * 40, True)
            for invalid in ("main", "--other", "a" * 39, "A" * 40):
                with self.assertRaises(ValueError): ci.resolve_source(invalid, False)

    def test_recovery_selects_latest_stage_from_correct_same_tap_workflow(self):
        run = {"repository": {"full_name": ci.REPOSITORY}, "head_branch": "main",
               "event": "workflow_dispatch", "path": ".github/workflows/release.yml"}
        artifacts = {"artifacts": [{"name": "testflight-state", "expired": False},
                                    {"name": "homebrew-state", "expired": False}]}
        with patch.object(ci, "github", side_effect=[run, artifacts]):
            self.assertEqual(ci.recovery_artifact("123"), "homebrew-state")
        artifacts["artifacts"][1]["expired"] = True
        with patch.object(ci, "github", side_effect=[run, artifacts]):
            self.assertEqual(ci.recovery_artifact("123"), "testflight-state")
        for key, value in (("head_branch", "feature"), ("event", "pull_request"),
                           ("repository", {"full_name": "other/tap"}), ("path", ".github/workflows/other.yml")):
            with patch.object(ci, "github", return_value=dict(run, **{key: value})):
                with self.assertRaises(ValueError): ci.recovery_artifact("123")
        with patch.object(ci, "github", side_effect=[run, {"artifacts": []}]):
            with self.assertRaisesRegex(ValueError, "do not repeat"):
                ci.recovery_artifact("123")
        with self.assertRaisesRegex(ValueError, "run ID"):
            ci.recovery_artifact("../escape")

    def test_publication_workflow_is_manual_verify_default_and_has_checkpoints(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertNotIn("pull_request:", workflow)
        self.assertNotIn("  push:", workflow)
        self.assertIn("default: verify", workflow)
        self.assertIn("runs-on: xcode-27", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("inputs.mode == 'release' && github.ref == 'refs/heads/main'", workflow)
        self.assertLess(workflow.index("name: testflight-state"), workflow.index("name: Sign and notarize"))
        self.assertNotIn("path: ${{ runner.temp }}/testflight-build", workflow)
        self.assertIn("name: homebrew-state", workflow)

if __name__ == "__main__": unittest.main()
