import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import textwrap
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ci

class InputTests(unittest.TestCase):
    def test_updater_report_requires_executed_suite_without_failures_or_skips(self):
        good = {"result": "passed", "passed": 1, "skipped": 0,
                "records": [{"id": "-[PositionBarAppTests.UpdateConfigurationTests testTapFeed]"}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            path.write_text(json.dumps(good))
            self.assertEqual(ci.verify_updater_report(path), 1)
            for changes in ({"result": "failed"}, {"skipped": 1}, {"passed": 0, "records": []},
                            {"records": [{"id": "-[OtherTests testOne]"}]}):
                with self.subTest(changes=changes):
                    path.write_text(json.dumps(dict(good, **changes)))
                    with self.assertRaisesRegex(ValueError, "must execute"):
                        ci.verify_updater_report(path)

    def test_source_requires_full_sha_and_current_main_only_for_fresh_release(self):
        with patch.object(ci, "github", return_value={"sha": "a" * 40}) as github:
            self.assertEqual(ci.resolve_source("b" * 40, False), "b" * 40)
            github.assert_not_called()
            self.assertEqual(ci.resolve_source("a" * 40, True), "a" * 40)
            with self.assertRaisesRegex(ValueError, "main SHA"):
                ci.resolve_source("b" * 40, True)
            for invalid in ("main", "--other", "a" * 39, "A" * 40):
                with self.assertRaises(ValueError): ci.resolve_source(invalid, False)

    def test_omitted_source_resolves_main_and_rejects_invalid_api_identity(self):
        with patch.object(ci, "github", return_value={"sha": "a" * 40}) as github:
            for publishing in (False, True):
                self.assertEqual(ci.resolve_source("", publishing), "a" * 40)
            github.assert_called_with("repos/sorcererxw/positionbar/commits/main")
        for value in (None, "main", "a" * 39, "A" * 40):
            with self.subTest(value=value), patch.object(ci, "github", return_value={"sha": value}):
                with self.assertRaisesRegex(ValueError, "full application source SHA"):
                    ci.resolve_source("", True)
        with patch.object(ci, "github", side_effect=[{"sha": "a" * 40}, {"sha": "b" * 40}]):
            with self.assertRaisesRegex(ValueError, "main SHA"):
                ci.resolve_source("", True)

    def test_recovery_selects_latest_stage_from_correct_same_tap_workflow(self):
        run = {"repository": {"full_name": ci.REPOSITORY}, "head_branch": "main",
               "event": "workflow_dispatch", "path": ".github/workflows/release.yml"}
        artifacts = {"artifacts": [{"name": "release-state", "expired": False},
                                    {"name": "homebrew-state", "expired": False}]}
        with patch.object(ci, "github", side_effect=[run, artifacts]):
            self.assertEqual(ci.recovery_artifact("123"), "homebrew-state")
        artifacts["artifacts"][1]["expired"] = True
        with patch.object(ci, "github", side_effect=[run, artifacts]):
            self.assertEqual(ci.recovery_artifact("123"), "release-state")
        for key, value in (("head_branch", "feature"), ("event", "pull_request"),
                           ("repository", {"full_name": "other/tap"}), ("path", ".github/workflows/other.yml")):
            with patch.object(ci, "github", return_value=dict(run, **{key: value})):
                with self.assertRaises(ValueError): ci.recovery_artifact("123")
        with patch.object(ci, "github", side_effect=[run, {"artifacts": []}]):
            with self.assertRaisesRegex(ValueError, "new release attempt"):
                ci.recovery_artifact("123")
        with self.assertRaisesRegex(ValueError, "run ID"):
            ci.recovery_artifact("../escape")

    def test_pr_source_verification_is_fixed_read_only_and_excludes_forks(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
        workflow = workflow.split("\n  release:\n", 1)[0]
        self.assertIn("github.event_name == 'pull_request'", workflow)
        self.assertIn("github.event.pull_request.head.repo.full_name == github.repository", workflow)
        self.assertIn("PR_SOURCE_SHA: dff62195853144f89da214aa7fdc1f23690fba57", workflow)
        self.assertIn("source/scripts/unified_release.py verify", workflow)
        self.assertIn("PositionBarAppTests.UpdateConfigurationTests", workflow)
        self.assertIn('source/scripts/check test-report "$RUNNER_TEMP/updater-tests.log"', workflow)
        self.assertIn('tap/scripts/ci.py tests --report "$RUNNER_TEMP/updater-tests.json"', workflow)
        self.assertNotIn("APP_STORE_API_PRIVATE_KEY", workflow)
        self.assertNotIn("DEVELOPER_ID_CERTIFICATE", workflow)
        self.assertNotIn("SPARKLE_PRIVATE_KEY", workflow)
        self.assertNotIn("contents: write", workflow)

    def test_source_step_blocks_non_main_publication_and_unidentified_recovery(self):
        workflow = (Path(__file__).resolve().parents[1] / ".github/workflows/release.yml").read_text()
        step = workflow.split("      - name: Resolve application source\n", 1)[1].split("      - uses:", 1)[0]
        script = textwrap.dedent(step.split("        run: |\n", 1)[1])
        with tempfile.TemporaryDirectory() as directory:
            for ref, resume, message in (("refs/heads/feature", "", "dispatch on main"),
                                         ("refs/heads/main", "123", "original source_sha")):
                with self.subTest(ref=ref, resume=resume):
                    output = Path(directory) / "output"
                    environment = {key: value for key, value in os.environ.items()
                                   if key not in ("GH_TOKEN", "GITHUB_TOKEN")}
                    environment.update(GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF=ref,
                                       DISPATCH_MODE="release", INPUT_SHA="", RESUME_RUN_ID=resume,
                                       GITHUB_OUTPUT=str(output))
                    result = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-e", "-o", "pipefail",
                                             "-c", script], cwd=directory, env=environment,
                                            capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn(message, result.stderr)
                    self.assertFalse(output.exists())

    def test_publication_workflow_is_manual_verify_default_and_has_checkpoints(self):
        workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
        self.assertEqual(sorted(path.name for path in workflows.glob("*.y*ml")), ["release.yml"])
        workflow = (workflows / "release.yml").read_text()
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("  push:", workflow)
        self.assertIn("default: verify", workflow)
        self.assertIn("runs-on: xcode-27", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("if: github.event_name == 'workflow_dispatch' && inputs.mode == 'release' && github.ref == 'refs/heads/main'", workflow)
        self.assertIn('[[ -z "$RESUME_RUN_ID" || -n "$INPUT_SHA" ]]', workflow)
        self.assertLess(workflow.index("name: release-state"), workflow.index("name: Sign and notarize"))
        self.assertNotIn("TESTFLIGHT_ENABLED", workflow)
        self.assertNotIn("APP_STORE_CERTIFICATES", workflow)
        self.assertNotIn("APP_STORE_PROFILE", workflow)
        self.assertIn("unified_release.py prepare", workflow)
        self.assertIn("name: homebrew-state", workflow)
        self.assertIn("PositionBar-*.dmg", workflow)
        self.assertNotIn("PositionBar-*.zip", workflow)
        self.assertIn('source/scripts/check test-report "$RUNNER_TEMP/updater-tests.log"', workflow)
        self.assertIn('tap/scripts/ci.py tests --report "$RUNNER_TEMP/updater-tests.json"', workflow)

if __name__ == "__main__": unittest.main()
