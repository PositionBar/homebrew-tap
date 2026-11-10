import base64
import copy
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cask


def receipt(version="0.1.0", build=1015, source="a" * 40, sha="b" * 64):
    tag = f"positionbar-{version}-{build}"
    name = f"PositionBar-{version}-{build}.zip"
    return {
        "schemaVersion": 1,
        "status": "artifact_published",
        "source": source,
        "version": version,
        "build": build,
        "registryStatus": "succeeded",
        "artifact": {
            "name": name,
            "url": f"https://github.com/PositionBar/homebrew-tap/releases/download/{tag}/{name}",
            "sha256": sha,
            "length": 123,
            "appName": "PositionBar.app",
            "bundleIdentifier": "com.positionbar.app",
            "architectures": ["arm64", "x86_64"],
            "minimumSystemVersion": "27.0.0",
            "teamID": "TX6HZR5RB7",
            "entitlements": {
                "com.apple.security.app-sandbox": True,
                "com.apple.security.network.client": True,
                "com.apple.security.network.server": True,
            },
            "developerIDVerified": True,
            "notarizationStatus": "Accepted",
            "stapled": True,
            "gatekeeperVerified": True,
            "sparkleEmbedded": True,
            "sparkleFeedURL": cask.SPARKLE_FEED_URL,
            "sparklePublicEDKey": base64.b64encode(b"k" * 32).decode(),
        },
        "githubRelease": {
            "repository": "PositionBar/homebrew-tap",
            "tag": tag,
            "status": "published",
            "appcast": f"https://github.com/PositionBar/homebrew-tap/releases/download/{tag}/appcast.xml",
        },
        "tap": {"repository": "PositionBar/homebrew-tap", "status": "pending"},
    }


class ReceiptTests(unittest.TestCase):
    def test_requires_completed_registered_build(self):
        value = receipt()
        value["registryStatus"] = "reserved"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "homebrew.json"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "not completed"):
                cask.load_receipt(path)

    def test_rejects_invalid_build_and_release_url(self):
        for mutation in (
            lambda value: value.update(build=0),
            lambda value: value["artifact"].update(
                url="https://github.com/another/tap/releases/download/tag/PositionBar.zip"
            ),
            lambda value: value["artifact"].update(sparkleEmbedded=False),
        ):
            value = receipt()
            mutation(value)
            with tempfile.TemporaryDirectory() as temporary:
                path = Path(temporary) / "homebrew.json"
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    cask.load_receipt(path)

    def test_rejects_missing_or_invalid_sparkle_publication(self):
        mutations = (
            lambda value: value["artifact"].pop("sparkleFeedURL"),
            lambda value: value["artifact"].update(sparkleFeedURL="https://example.com/appcast.xml"),
            lambda value: value["artifact"].pop("sparklePublicEDKey"),
            lambda value: value["artifact"].update(sparklePublicEDKey="invalid!"),
            lambda value: value["artifact"].update(sparklePublicEDKey=base64.b64encode(b"short").decode()),
            lambda value: value["githubRelease"].pop("appcast"),
            lambda value: value["githubRelease"].update(appcast=cask.SPARKLE_FEED_URL),
            lambda value: value["githubRelease"].update(tag="positionbar-0.1.0-1016"),
            lambda value: value.pop("registryStatus"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index), tempfile.TemporaryDirectory() as temporary:
                value = receipt()
                mutate(value)
                path = Path(temporary) / "homebrew.json"
                path.write_text(json.dumps(value))
                with self.assertRaises(ValueError):
                    cask.load_receipt(path)

    def test_accepts_same_source_version_and_build_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "homebrew.json"
            path.write_text(json.dumps(receipt()))
            loaded = cask.load_receipt(path)
        self.assertEqual(loaded["source"], "a" * 40)
        self.assertEqual((loaded["version"], loaded["build"]), ("0.1.0", 1015))


class RenderingTests(unittest.TestCase):
    def test_universal_cask_has_no_arch_restriction(self):
        contents = cask.render_cask(receipt(), "golden_gate")
        self.assertIn('  version "0.1.0,1015"\n', contents)
        self.assertIn("  depends_on macos: :golden_gate\n", contents)
        self.assertNotIn("depends_on arch:", contents)
        self.assertIn("  auto_updates true\n", contents)

    def test_single_arch_cask_declares_arch(self):
        value = receipt()
        value["artifact"]["architectures"] = ["arm64"]
        self.assertIn("  depends_on arch: :arm64\n", cask.render_cask(value, "golden_gate"))

    def test_candidate_identity_is_idempotent_and_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Casks/positionbar.rb"
            first = cask.render_cask(receipt(), "golden_gate")
            metadata = first.replace(
                "Read-only multi-account position monitor",
                "Menu bar portfolio and position monitor",
            )
            changed_sha = receipt(sha="c" * 64)
            moved = receipt()
            moved["artifact"]["url"] = moved["artifact"]["url"].replace("PositionBar-", "Renamed-")
            newer = receipt(version="0.1.1", build=1016)
            self.assertTrue(cask.write_candidate(path, first))
            self.assertFalse(cask.write_candidate(path, first))
            self.assertTrue(cask.write_candidate(path, metadata))
            with self.assertRaisesRegex(ValueError, "URL or SHA-256"):
                cask.write_candidate(path, cask.render_cask(changed_sha, "golden_gate"))
            with self.assertRaisesRegex(ValueError, "URL or SHA-256"):
                cask.write_candidate(path, cask.render_cask(moved, "golden_gate"))
            self.assertTrue(cask.write_candidate(path, cask.render_cask(newer, "golden_gate")))
            with self.assertRaisesRegex(ValueError, "downgrade"):
                cask.write_candidate(path, first)

    def test_release_record_cannot_change_source_or_artifact(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Releases/positionbar.rb"
            self.assertTrue(cask.write_record(path, cask.release_record(receipt())))
            self.assertFalse(cask.write_record(path, cask.release_record(receipt())))
            with self.assertRaisesRegex(ValueError, "source differs"):
                cask.write_record(path, cask.release_record(receipt(source="c" * 40)))
            with self.assertRaisesRegex(ValueError, "artifact differs"):
                cask.write_record(path, cask.release_record(receipt(sha="d" * 64)))

    def test_release_record_preserves_and_locks_sparkle_publication(self):
        original = cask.release_record(receipt())
        self.assertEqual(original["githubRelease"], receipt()["githubRelease"])
        self.assertEqual(original["artifact"]["sparklePublicEDKey"], receipt()["artifact"]["sparklePublicEDKey"])
        mutations = (
            ("artifact", "length", 124),
            ("artifact", "sparklePublicEDKey", base64.b64encode(b"z" * 32).decode()),
            ("artifact", "sparkleFeedURL", "https://example.com/appcast.xml"),
            ("githubRelease", "appcast", "https://example.com/appcast.xml"),
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "record.json"
            cask.write_record(path, original)
            for section, key, replacement in mutations:
                with self.subTest(section=section, key=key):
                    changed = copy.deepcopy(original)
                    changed[section][key] = replacement
                    with self.assertRaises(ValueError):
                        cask.write_record(path, changed)
                    self.assertEqual(json.loads(path.read_text()), original)
            for key, replacement in (("source", "c" * 40), ("version", "0.1.1"), ("build", 1016)):
                changed = copy.deepcopy(original)
                changed[key] = replacement
                with self.assertRaises(ValueError):
                    cask.write_record(path, changed)


class ArtifactTests(unittest.TestCase):
    def test_rejects_disabled_or_mismatched_app_updates(self):
        cases = (
            ("PBUpdatesEnabled", "NO", "disables in-app updates"),
            ("SUFeedURL", "https://example.com/feed.xml", "Sparkle feed differs"),
            ("SUPublicEDKey", "wrong-key", "Sparkle key differs"),
            ("framework", False, "missing Sparkle"),
        )
        for key, replacement, error in cases:
            with self.subTest(field=key), tempfile.TemporaryDirectory() as temporary:
                archive = Path(temporary) / "fixture.zip"
                archive.write_bytes(b"synthetic")
                value = receipt(sha=cask.digest(archive))
                value["artifact"]["length"] = archive.stat().st_size

                def fake_run(*args, capture=False):
                    if args[0] == "ditto":
                        contents = args[-1] / "PositionBar.app/Contents"
                        contents.mkdir(parents=True)
                        if key != "framework":
                            (contents / "Frameworks/Sparkle.framework").mkdir(parents=True)
                        info = {
                            "CFBundleIdentifier": "com.positionbar.app",
                            "CFBundleShortVersionString": "0.1.0",
                            "CFBundleVersion": "1015",
                            "PBSourceRevision": "a" * 40,
                            "PBBuildID": "1015",
                            "PBSourceDirty": False,
                            "LSMinimumSystemVersion": "27.0",
                            "PBUpdatesEnabled": "YES",
                            "SUFeedURL": value["artifact"]["sparkleFeedURL"],
                            "SUPublicEDKey": value["artifact"]["sparklePublicEDKey"],
                        }
                        if key != "framework":
                            info[key] = replacement
                        (contents / "Info.plist").write_bytes(plistlib.dumps(info))
                    return ""

                with patch.object(cask, "run", side_effect=fake_run):
                    with self.assertRaisesRegex(ValueError, error):
                        cask.verify_artifact(archive, value)

    def test_artifact_verification_checks_contents_and_platform_trust(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            work = root / "work/PositionBar.app/Contents"
            (work / "MacOS").mkdir(parents=True)
            (work / "Frameworks/Sparkle.framework").mkdir(parents=True)
            (work / "MacOS/PositionBar").write_bytes(b"synthetic")
            entitlements = receipt()["artifact"]["entitlements"]
            (work / "Info.plist").write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleIdentifier": "com.positionbar.app",
                        "CFBundleShortVersionString": "0.1.0",
                        "CFBundleVersion": "1015",
                        "LSMinimumSystemVersion": "27.0",
                        "PBUpdatesEnabled": "YES",
                        "SUFeedURL": cask.SPARKLE_FEED_URL,
                        "SUPublicEDKey": receipt()["artifact"]["sparklePublicEDKey"],
                        "PBSourceRevision": "a" * 40,
                        "PBBuildID": "1015",
                        "PBSourceDirty": False,
                    }
                )
            )
            archive = root / "PositionBar.zip"
            # This is a synthetic bundle, not a macOS signing/extraction test.
            # Keep tap regressions runnable on the Ubuntu pull-request runner.
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as fixture:
                for path in (root / "work").rglob("*"):
                    fixture.write(path, path.relative_to(root / "work").as_posix())
            value = receipt()
            value["artifact"]["sha256"] = hashlib.sha256(archive.read_bytes()).hexdigest()
            value["artifact"]["length"] = archive.stat().st_size

            def fake_run(*args, capture=False):
                if args[0] == "ditto":
                    with zipfile.ZipFile(args[-2]) as fixture:
                        fixture.extractall(args[-1])
                    return ""
                if args[:3] == ("codesign", "-d", "--entitlements"):
                    return plistlib.dumps(entitlements).decode()
                if args[0] == "lipo":
                    return "arm64 x86_64\n"
                return ""

            with patch.object(cask, "run", side_effect=fake_run):
                facts = cask.verify_artifact(archive, value)
        self.assertEqual(facts["minimumSystemVersion"], "27.0.0")
        self.assertEqual(facts["architectures"], ("arm64", "x86_64"))


class LocalGitPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.remote = root / "remote.git"
        self.repo = root / "tap"
        subprocess.run(["git", "init", "--bare", "-b", "main", self.remote], check=True)
        subprocess.run(["git", "init", "-b", "main", self.repo], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "Cask Test"], check=True)
        subprocess.run(
            ["git", "-C", self.repo, "config", "user.email", "cask-test@example.invalid"],
            check=True,
        )
        (self.repo / "README.md").write_text("Tap fixture\n")
        subprocess.run(["git", "-C", self.repo, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-m", "Initial tap"], check=True)
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin", self.remote], check=True)
        subprocess.run(["git", "-C", self.repo, "push", "-u", "origin", "main"], check=True)
        self.receipt_path = root / "homebrew.json"
        self.receipt_path.write_text(json.dumps(receipt()))
        self.cask_path = self.repo / "Casks/positionbar.rb"
        self.records = self.repo / "Releases"
        self.style = Mock()
        for target, attribute, value in (
            (cask, "ROOT", self.repo),
            (cask, "CASK", self.cask_path),
            (cask, "RELEASES", self.records),
            (cask, "download", Mock()),
            (cask, "verify_artifact", Mock(return_value={
                "minimumSystemVersion": "27.0.0",
                "architectures": ("arm64", "x86_64"),
                "appName": "PositionBar.app",
            })),
            (cask, "homebrew_macos_symbol", Mock(return_value="golden_gate")),
            (cask, "run_brew_style", self.style),
        ):
            patcher = patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_dry_run_never_downloads_or_touches_git(self):
        with patch.object(cask, "download") as download, patch.object(cask, "run") as run:
            result = cask.publish(self.receipt_path)
        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["source"], "a" * 40)
        download.assert_not_called()
        run.assert_not_called()

    def test_publish_commits_cask_and_pairing_record(self):
        result = cask.publish(self.receipt_path, execute=True)
        self.assertEqual(result["status"], "pushed")
        self.assertEqual(result["source"], "a" * 40)
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", self.repo, "show", "origin/main:Casks/positionbar.rb"],
                text=True,
            ),
            self.cask_path.read_text(),
        )
        record = json.loads(
            subprocess.check_output(
                ["git", "-C", self.repo, "show", "origin/main:Releases/positionbar-0.1.0-1015.json"],
                text=True,
            )
        )
        self.assertEqual((record["source"], record["version"], record["build"]), ("a" * 40, "0.1.0", 1015))
        self.style.assert_called_once_with(self.cask_path)
        repeated = cask.publish(self.receipt_path, execute=True)
        self.assertEqual(repeated["status"], "already published")

    def test_failed_push_retries_without_duplicate_commit(self):
        real_run = cask.run
        attempts = {"push": 0}

        def fail_first_push(*args, capture=False):
            if args[3:5] == ("push", "origin") and attempts["push"] == 0:
                attempts["push"] += 1
                raise subprocess.CalledProcessError(1, args)
            return real_run(*args, capture=capture)

        with patch.object(cask, "run", side_effect=fail_first_push):
            with self.assertRaisesRegex(ValueError, "publication state is uncertain"):
                cask.publish(self.receipt_path, execute=True)
            local = subprocess.check_output(["git", "-C", self.repo, "rev-parse", "HEAD"], text=True).strip()
            remote = subprocess.check_output(["git", "-C", self.remote, "rev-parse", "main"], text=True).strip()
            self.assertNotEqual(local, remote)
            result = cask.publish(self.receipt_path, execute=True)
        self.assertEqual(result["status"], "pushed")
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", self.remote, "rev-list", "--count", "main"],
                text=True,
            ).strip(),
            "2",
        )

    def test_commit_failure_recovers_own_staged_candidate(self):
        real_run = cask.run
        attempts = {"commit": 0}

        def fail_first_commit(*args, capture=False):
            if args[3:5] == ("commit", "-m") and attempts["commit"] == 0:
                attempts["commit"] += 1
                raise subprocess.CalledProcessError(1, args)
            return real_run(*args, capture=capture)

        with patch.object(cask, "run", side_effect=fail_first_commit):
            with self.assertRaises(subprocess.CalledProcessError):
                cask.publish(self.receipt_path, execute=True)
            self.assertTrue(self.cask_path.is_file())
            self.assertTrue(
                subprocess.check_output(
                    ["git", "-C", self.repo, "status", "--porcelain"],
                    text=True,
                ).strip()
            )
            result = cask.publish(self.receipt_path, execute=True)
        self.assertEqual(result["status"], "pushed")
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", self.remote, "rev-list", "--count", "main"],
                text=True,
            ).strip(),
            "2",
        )

    def test_cli_keeps_command_logs_out_of_machine_result(self):
        wrapper = Path(self.temp.name) / "cask-wrapper.py"
        wrapper.write_text(
            f"""import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("real_cask", {str(ROOT / "scripts/cask.py")!r})
cask = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cask)
cask.ROOT = Path(os.environ["FIXTURE_REPO"]).resolve()
cask.CASK = cask.ROOT / "Casks/positionbar.rb"
cask.RELEASES = cask.ROOT / "Releases"
cask.download = lambda *args: None
cask.verify_artifact = lambda *args: {{
    "minimumSystemVersion": "27.0.0",
    "architectures": ("arm64", "x86_64"),
    "appName": "PositionBar.app",
}}
cask.homebrew_macos_symbol = lambda version: "golden_gate"
cask.publication_git_state = lambda *args: "current"
def brew_style(path):
    cask.run("sh", "-c", "printf 'brew style log\\\\n'; printf 'brew style warning\\\\n' >&2")
cask.run_brew_style = brew_style
cask.main()
"""
        )
        result_path = Path(self.temp.name) / "cask-result.json"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                wrapper,
                "publish",
                "--receipt",
                self.receipt_path,
                "--execute",
                "--result",
                result_path,
            ],
            env=dict(os.environ, FIXTURE_REPO=str(self.repo)),
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        stdout = json.loads(result.stdout)
        stored = json.loads(result_path.read_text())
        self.assertEqual(stdout, stored)
        self.assertEqual(stored["status"], "pushed")
        self.assertNotIn("brew style log", result.stdout)
        self.assertIn("brew style log", result.stderr)
        self.assertIn("brew style warning", result.stderr)


if __name__ == "__main__":
    unittest.main()
