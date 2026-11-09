import base64
import hashlib
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import cask


class CaskRenderingTests(unittest.TestCase):
    def test_universal_release_renders_one_cask_without_arch_restriction(self):
        release = {
            "version": "0.1.1",
            "build": 2,
            "artifact": {
                "url": "https://positionbar.com/updates/macos/releases/0.1.1/2/PositionBar-0.1.1-2.zip",
                "sha256": "a" * 64,
            },
        }

        self.assertEqual(
            cask.render_cask(release, "PositionBar.app", ("arm64", "x86_64"), "golden_gate"),
            '''cask "positionbar" do
  version "0.1.1,2"
  sha256 "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

  url "https://positionbar.com/updates/macos/releases/0.1.1/2/PositionBar-0.1.1-2.zip"
  name "PositionBar"
  desc "Read-only multi-account position monitor"
  homepage "https://positionbar.com/"

  depends_on macos: :golden_gate

  app "PositionBar.app"
end
''',
        )

    def test_single_architecture_release_declares_its_arch(self):
        release = {
            "version": "0.1.1",
            "build": 2,
            "artifact": {
                "url": "https://positionbar.com/updates/macos/releases/0.1.1/2/PositionBar-0.1.1-2.zip",
                "sha256": "a" * 64,
            },
        }

        self.assertIn(
            '  depends_on arch: :arm64\n',
            cask.render_cask(release, "PositionBar.app", ("arm64",), "golden_gate"),
        )


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.stage = Path(self.temp.name) / "stage"
        self.stage.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_fixture(self):
        work = self.stage / "work"
        contents = work / "PositionBar.app/Contents"
        macos = contents / "MacOS"
        macos.mkdir(parents=True)
        source = work / "main.c"
        source.write_text("int main(void) { return 0; }\n")
        binary = macos / "PositionBar"
        subprocess.run(
            ["cc", "-arch", "arm64", "-arch", "x86_64", source, "-o", binary],
            check=True,
        )

        feed_url = "https://positionbar.com/updates/macos/appcast.xml"
        public_key = base64.b64encode(bytes(32)).decode()
        signature = base64.b64encode(bytes(64)).decode()
        version = "0.1.1"
        build = 2
        archive = self.stage / "PositionBar-0.1.1-2.zip"
        artifact_url = (
            "https://positionbar.com/updates/macos/releases/0.1.1/2/"
            + archive.name
        )
        notes_url = artifact_url[:-4] + ".txt"

        info = {
            "CFBundleIdentifier": "com.positionbar.app",
            "CFBundleExecutable": "PositionBar",
            "CFBundleName": "PositionBar",
            "CFBundlePackageType": "APPL",
            "CFBundleVersion": str(build),
            "CFBundleShortVersionString": version,
            "LSMinimumSystemVersion": "27.0.0",
            "SUPublicEDKey": public_key,
            "SUFeedURL": feed_url,
            "PBUpdatesEnabled": "YES",
            "SUVerifyUpdateBeforeExtraction": True,
            "SURequireSignedFeed": True,
            "SUEnableAutomaticChecks": False,
            "SUAutomaticallyUpdate": False,
            "SUEnableSystemProfiling": False,
        }
        (contents / "Info.plist").write_bytes(plistlib.dumps(info))
        subprocess.run(
            ["ditto", "-c", "-k", "--keepParent", work / "PositionBar.app", archive],
            check=True,
        )
        archive_sha = hashlib.sha256(archive.read_bytes()).hexdigest()

        notes = self.stage / "PositionBar-0.1.1-2.txt"
        notes.write_text("PositionBar 0.1.1\n")
        feed_content = f'''<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:sparkle="{cask.SPARKLE_NS}">
  <channel>
    <item>
      <sparkle:version>{build}</sparkle:version>
      <sparkle:shortVersionString>{version}</sparkle:shortVersionString>
      <sparkle:minimumSystemVersion>27.0.0</sparkle:minimumSystemVersion>
      <enclosure url="{artifact_url}" sparkle:edSignature="{signature}" length="{archive.stat().st_size}"/>
      <sparkle:releaseNotesLink sparkle:edSignature="{signature}" sparkle:length="{notes.stat().st_size}">{notes_url}</sparkle:releaseNotesLink>
    </item>
  </channel>
</rss>
'''.encode()
        feed = self.stage / "appcast.xml"
        feed.write_bytes(
            feed_content
            + b"<!-- sparkle-signatures:\n"
            + f"edSignature: {signature}\nlength: {len(feed_content)}\n".encode()
            + b"-->"
        )

        release = {
            "version": version,
            "build": build,
            "status": "draft",
            "publishedOn": "2026-11-09",
            "changes": [],
            "artifact": {
                "url": artifact_url,
                "notesURL": notes_url,
                "sha256": archive_sha,
                "edSignature": signature,
                "length": archive.stat().st_size,
            },
        }
        manifest = {
            "sourceSHA256": "b" * 64,
            "release": release,
            "feedURL": feed_url,
            "previousFeedSHA256": None,
            "publicKey": public_key,
            "objectPrefix": "releases/0.1.1/2/",
            "files": {
                archive.name: archive_sha,
                notes.name: hashlib.sha256(notes.read_bytes()).hexdigest(),
                feed.name: hashlib.sha256(feed.read_bytes()).hexdigest(),
            },
        }
        prepared = self.stage / "prepared.json"
        prepared.write_text(json.dumps(manifest))
        return prepared

    @patch.object(cask, "verify_authenticity")
    def test_valid_stage_derives_release_facts_from_contract_and_artifact(self, verify):
        prepared = self.write_fixture()

        result = cask.inspect_stage(prepared, Path("/source"))

        self.assertEqual(result["release"]["version"], "0.1.1")
        self.assertEqual(result["release"]["build"], 2)
        self.assertEqual(result["app_name"], "PositionBar.app")
        self.assertEqual(result["architectures"], ("arm64", "x86_64"))
        self.assertEqual(result["minimumSystemVersion"], "27.0.0")
        verify.assert_called_once()

    @patch.object(cask, "verify_authenticity")
    def test_modified_archive_is_rejected_before_path_publish(self, verify):
        prepared = self.write_fixture()
        with (self.stage / "PositionBar-0.1.1-2.zip").open("ab") as archive:
            archive.write(b"tampered")

        with self.assertRaisesRegex(ValueError, "SHA-256"):
            cask.inspect_stage(prepared, Path("/source"))
        verify.assert_not_called()

    @patch.object(cask, "verify_authenticity")
    def test_missing_archive_is_rejected(self, verify):
        prepared = self.write_fixture()
        (self.stage / "PositionBar-0.1.1-2.zip").unlink()

        with self.assertRaisesRegex(ValueError, "Prepared file is missing"):
            cask.inspect_stage(prepared, Path("/source"))
        verify.assert_not_called()

    @patch.object(cask, "verify_authenticity")
    def test_app_and_feed_minimum_versions_must_match(self, verify):
        prepared = self.write_fixture()
        feed = self.stage / "appcast.xml"
        feed.write_bytes(
            feed.read_bytes().replace(
                b"<sparkle:minimumSystemVersion>27.0.0</sparkle:minimumSystemVersion>",
                b"<sparkle:minimumSystemVersion>26.0.0</sparkle:minimumSystemVersion>",
            )
        )
        manifest = json.loads(prepared.read_text())
        manifest["files"]["appcast.xml"] = hashlib.sha256(feed.read_bytes()).hexdigest()
        prepared.write_text(json.dumps(manifest))

        with self.assertRaisesRegex(ValueError, "minimum system"):
            cask.inspect_stage(prepared, Path("/source"))
        verify.assert_not_called()

    @patch.object(cask, "load_source_contract")
    def test_authenticity_reuses_source_repository_verifiers(self, load_contract):
        prepared = self.write_fixture()
        manifest = json.loads(prepared.read_text())
        release = manifest["release"]
        archive = self.stage / "PositionBar-0.1.1-2.zip"
        notes = self.stage / "PositionBar-0.1.1-2.txt"
        feed = self.stage / "appcast.xml"
        app = self.stage / "work/PositionBar.app"
        release_contract = unittest.mock.Mock()
        releases_contract = unittest.mock.Mock()
        releases_contract.verify_appcast.return_value = {
            "edSignature": release["artifact"]["edSignature"],
            "length": release["artifact"]["length"],
        }
        load_contract.return_value = (release_contract, releases_contract, "TX6HZR5RB7")

        cask.verify_authenticity(
            manifest,
            release,
            archive,
            notes,
            feed,
            app,
            "27.0.0",
            Path("/source"),
        )

        release_contract.verify_feed.assert_called_once()
        release_contract.verify_bytes.assert_called_once()
        release_contract.verify_notes.assert_called_once()
        release_contract.verify_app.assert_called_once()
        releases_contract.verify_appcast.assert_called_once()

    @patch.object(cask, "homebrew_macos_symbol", return_value="golden_gate")
    @patch.object(cask, "verify_authenticity")
    def test_valid_stage_generates_cask_from_artifact_facts(self, verify, symbol):
        del verify, symbol
        prepared = self.write_fixture()

        stage = cask.candidate(prepared, Path("/source"))
        output = Path(self.temp.name) / "Casks/positionbar.rb"
        self.assertTrue(cask.write_candidate(output, stage["contents"]))

        contents = output.read_text()
        self.assertIn('  version "0.1.1,2"\n', contents)
        self.assertIn('  depends_on macos: :golden_gate\n', contents)
        self.assertIn('  app "PositionBar.app"\n', contents)
        self.assertNotIn("depends_on arch:", contents)


class CandidateTests(unittest.TestCase):
    def release(self, version="0.1.1", build=2, sha="a" * 64):
        return {
            "version": version,
            "build": build,
            "artifact": {
                "url": f"https://positionbar.com/updates/macos/releases/{version}/{build}/PositionBar-{version}-{build}.zip",
                "sha256": sha,
            },
        }

    def test_candidate_write_is_idempotent_and_protects_artifact_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "Casks/positionbar.rb"
            first = cask.render_cask(self.release(), "PositionBar.app", ("arm64", "x86_64"), "golden_gate")
            metadata = first.replace(
                "Read-only multi-account position monitor",
                "Menu bar portfolio and position monitor",
            )
            changed = cask.render_cask(self.release(sha="b" * 64), "PositionBar.app", ("arm64", "x86_64"), "golden_gate")
            moved = self.release()
            moved["artifact"]["url"] = (
                "https://positionbar.com/updates/macos/releases/0.1.1/2/PositionBar-renamed.zip"
            )
            newer = cask.render_cask(self.release("0.1.2", 3), "PositionBar.app", ("arm64", "x86_64"), "golden_gate")

            self.assertTrue(cask.write_candidate(path, first))
            self.assertFalse(cask.write_candidate(path, first))
            self.assertTrue(cask.write_candidate(path, metadata))
            with self.assertRaisesRegex(ValueError, "URL or SHA-256"):
                cask.write_candidate(path, changed)
            with self.assertRaisesRegex(ValueError, "URL or SHA-256"):
                cask.write_candidate(
                    path,
                    cask.render_cask(moved, "PositionBar.app", ("arm64", "x86_64"), "golden_gate"),
                )
            self.assertTrue(cask.write_candidate(path, newer))
            with self.assertRaisesRegex(ValueError, "downgrade"):
                cask.write_candidate(path, first)

    def test_publish_is_dry_run_by_default(self):
        result = cask.publish(Path("/missing/prepared.json"), execute=False)

        self.assertEqual(result["mode"], "dry-run")
        self.assertEqual(result["status"], "not run")

    @patch.object(cask, "load_source_contract")
    def test_catalog_must_mark_the_exact_release_published(self, load_contract):
        releases_contract = unittest.mock.Mock()
        releases_contract.load.return_value = {}
        releases_contract.release.return_value = {
            "version": "0.1.1",
            "build": 2,
            "status": "draft",
            "publishedOn": None,
            "artifact": None,
        }
        load_contract.return_value = (unittest.mock.Mock(), releases_contract, "TX6HZR5RB7")
        release = self.release()

        with self.assertRaisesRegex(ValueError, "not marked published"):
            cask.verify_catalog_release(release, Path("/source"), Path("/catalog.json"))

    @patch.object(cask, "fetch", return_value=b"different public bytes")
    @patch.object(cask, "verify_catalog_release")
    @patch.object(cask, "candidate")
    def test_publish_rejects_public_checksum_mismatch_before_git(self, candidate, catalog, fetch):
        del catalog, fetch
        release = self.release()
        candidate.return_value = {
            "release": release,
            "app_name": "PositionBar.app",
            "architectures": ("arm64", "x86_64"),
            "minimumSystemVersion": "27.0.0",
            "minimumSymbol": "golden_gate",
            "contents": "",
        }

        with patch.object(cask, "run") as run:
            with self.assertRaisesRegex(ValueError, "Public artifact SHA-256"):
                cask.publish(
                    Path("/prepared.json"),
                    execute=True,
                    source_repo=Path("/source"),
                )
        run.assert_not_called()

    def test_homebrew_macos_symbol_comes_from_local_brew_contract(self):
        self.assertEqual(cask.homebrew_macos_symbol("27.0.0"), "golden_gate")

    def test_cli_exits_nonzero_for_missing_prepared_file(self):
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(ROOT / "scripts/cask.py"),
                "check",
                "--prepared",
                "/missing/prepared.json",
                "--positionbar-repo",
                "/missing/source",
            ],
            text=True,
            capture_output=True,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("prepared.json", result.stderr)


class LocalGitPublishTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.remote = root / "remote.git"
        self.repo = root / "tap"
        subprocess.run(["git", "init", "--bare", "-b", "main", self.remote], check=True)
        subprocess.run(["git", "init", "-b", "main", self.repo], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.name", "Cask Test"], check=True)
        subprocess.run(["git", "-C", self.repo, "config", "user.email", "cask-test@example.invalid"], check=True)
        (self.repo / "README.md").write_text("Tap fixture\n")
        subprocess.run(["git", "-C", self.repo, "add", "README.md"], check=True)
        subprocess.run(["git", "-C", self.repo, "commit", "-m", "Initial tap"], check=True)
        subprocess.run(["git", "-C", self.repo, "remote", "add", "origin", self.remote], check=True)
        subprocess.run(["git", "-C", self.repo, "push", "-u", "origin", "main"], check=True)

        public_bytes = b"published PositionBar artifact"
        release = {
            "version": "0.1.1",
            "build": 2,
            "publishedOn": "2026-11-09",
            "artifact": {
                "url": "https://positionbar.com/updates/macos/releases/0.1.1/2/PositionBar-0.1.1-2.zip",
                "sha256": hashlib.sha256(public_bytes).hexdigest(),
            },
        }
        contents = cask.render_cask(
            release,
            "PositionBar.app",
            ("arm64", "x86_64"),
            "golden_gate",
        )
        self.stage = {
            "release": release,
            "app_name": "PositionBar.app",
            "architectures": ("arm64", "x86_64"),
            "minimumSystemVersion": "27.0.0",
            "minimumSymbol": "golden_gate",
            "contents": contents,
        }
        self.cask_path = self.repo / "Casks/positionbar.rb"
        self.brew_style = unittest.mock.Mock()
        for target, attribute, value in (
            (cask, "ROOT", self.repo),
            (cask, "CASK", self.cask_path),
            (cask, "candidate", unittest.mock.Mock(return_value=self.stage)),
            (cask, "verify_catalog_release", unittest.mock.Mock()),
            (cask, "fetch", unittest.mock.Mock(return_value=public_bytes)),
            (cask, "run_brew_style", self.brew_style),
        ):
            patcher = patch.object(target, attribute, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_generate_then_publish_commits_and_pushes_existing_candidate(self):
        self.assertTrue(cask.write_candidate(self.cask_path, self.stage["contents"]))

        result = cask.publish(
            Path("/prepared.json"),
            execute=True,
            source_repo=Path("/source"),
        )

        self.assertEqual(result["status"], "pushed")
        remote_file = subprocess.check_output(
            ["git", "-C", self.repo, "show", "origin/main:Casks/positionbar.rb"],
            text=True,
        )
        self.assertEqual(remote_file, self.stage["contents"])
        self.brew_style.assert_called_once_with(self.cask_path)
        repeated = cask.publish(
            Path("/prepared.json"),
            execute=True,
            source_repo=Path("/source"),
        )
        self.assertEqual(repeated["status"], "already published")

    def test_failed_push_recovers_existing_local_commit_without_duplication(self):
        self.assertTrue(cask.write_candidate(self.cask_path, self.stage["contents"]))
        real_run = cask.run
        attempts = {"push": 0}

        def fail_first_push(*args, capture=False):
            if args[3:5] == ("push", "origin") and attempts["push"] == 0:
                attempts["push"] += 1
                raise subprocess.CalledProcessError(1, args)
            return real_run(*args, capture=capture)

        with patch.object(cask, "run", side_effect=fail_first_push):
            with self.assertRaisesRegex(ValueError, "publication state is uncertain"):
                cask.publish(
                    Path("/prepared.json"),
                    execute=True,
                    source_repo=Path("/source"),
                )
            local_commit = subprocess.check_output(
                ["git", "-C", self.repo, "rev-parse", "HEAD"],
                text=True,
            ).strip()
            remote_commit = subprocess.check_output(
                ["git", "-C", self.remote, "rev-parse", "main"],
                text=True,
            ).strip()
            self.assertNotEqual(local_commit, remote_commit)

            result = cask.publish(
                Path("/prepared.json"),
                execute=True,
                source_repo=Path("/source"),
            )

        self.assertEqual(result["status"], "pushed")
        self.assertEqual(
            subprocess.check_output(
                ["git", "-C", self.remote, "rev-list", "--count", "main"],
                text=True,
            ).strip(),
            "2",
        )


if __name__ == "__main__":
    unittest.main()
