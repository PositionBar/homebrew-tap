#!/usr/bin/env python3
"""Verify a paired PositionBar cask release and publish its cask locally."""

import argparse
import hashlib
import json
import plistlib
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
CASK = ROOT / "Casks/positionbar.rb"
RELEASES = ROOT / "Releases"
ACCEPTED = "upload_accepted_processing_pending"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def run(*args, capture=False):
    result = subprocess.run(
        [str(value) for value in args],
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else sys.stderr,
        stderr=subprocess.PIPE if capture else sys.stderr,
    )
    return result.stdout if capture else ""


def load_receipt(path):
    receipt = json.loads(Path(path).read_text())
    require(receipt.get("schemaVersion") == 1, "Unsupported cask receipt schema")
    require(
        receipt.get("status") in ("artifact_published", "cask_pending", "published"),
        "Cask receipt has not reached artifact publication",
    )
    source = receipt.get("source", "")
    require(re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", source), "Invalid source commit")
    version = receipt.get("version", "")
    build = receipt.get("build")
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "Invalid marketing version")
    require(type(build) is int and build > 0, "Invalid cask build")
    testflight = receipt.get("testFlight", {})
    require(testflight.get("status") == ACCEPTED, "TestFlight has not accepted this build")
    require(testflight.get("build") == str(build), "TestFlight build differs from cask build")
    require(str(testflight.get("buildID")) == str(build), "TestFlight and cask build IDs differ")
    artifact = receipt.get("artifact")
    require(isinstance(artifact, dict), "Cask artifact receipt is missing")
    for key in (
        "url",
        "sha256",
        "length",
        "name",
        "appName",
        "bundleIdentifier",
        "architectures",
        "minimumSystemVersion",
        "teamID",
        "entitlements",
    ):
        require(key in artifact, "Cask artifact field is missing: " + key)
    require(artifact["bundleIdentifier"] == "com.positionbar.app", "Bundle identifier changed")
    require(artifact["appName"] == "PositionBar.app", "App bundle name changed")
    require(artifact.get("developerIDVerified") is True, "Developer ID was not verified")
    require(artifact.get("notarizationStatus") == "Accepted", "Notarization was not accepted")
    require(artifact.get("stapled") is True, "Notarization ticket was not stapled")
    require(artifact.get("gatekeeperVerified") is True, "Gatekeeper was not verified")
    require(artifact.get("sparkleEmbedded") is False, "Cask artifact unexpectedly embeds Sparkle")
    require(re.fullmatch(r"[a-f0-9]{64}", artifact.get("sha256", "")), "Invalid cask SHA-256")
    require(type(artifact.get("length")) is int and artifact["length"] > 0, "Invalid cask length")
    architectures = artifact.get("architectures")
    require(
        architectures in (["arm64"], ["x86_64"], ["arm64", "x86_64"]),
        "Unsupported cask architectures",
    )
    minimum = artifact.get("minimumSystemVersion", "")
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", minimum), "Invalid minimum macOS version")
    require(artifact.get("teamID") == "TX6HZR5RB7", "Cask Team ID changed")
    release = receipt.get("githubRelease", {})
    require(release.get("repository") == "PositionBar/homebrew-tap", "Unexpected cask release repository")
    tag = release.get("tag", "")
    require(re.fullmatch(r"positionbar-[0-9]+\.[0-9]+\.[0-9]+-[0-9]+", tag), "Invalid cask release tag")
    parsed = urllib.parse.urlparse(artifact["url"])
    expected_path = f"/PositionBar/homebrew-tap/releases/download/{tag}/{artifact['name']}"
    require(
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.path == expected_path
        and not parsed.query
        and not parsed.fragment,
        "Cask URL does not match its GitHub release",
    )
    return receipt


def download(url, destination, expected_sha, expected_length):
    parsed = urllib.parse.urlparse(url)
    require(parsed.scheme == "https" and parsed.hostname == "github.com", "Unexpected cask URL")
    request = urllib.request.Request(url, headers={"User-Agent": "PositionBar-Homebrew-tap"})
    value = hashlib.sha256()
    length = 0
    with urllib.request.urlopen(request, timeout=90) as response:
        final = urllib.parse.urlparse(response.geturl())
        require(
            final.scheme == "https"
            and final.hostname
            in ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"),
            "Cask download redirected outside GitHub",
        )
        require(response.status == 200, "Cask artifact is unavailable")
        with Path(destination).open("wb") as target:
            for block in iter(lambda: response.read(1024 * 1024), b""):
                value.update(block)
                length += len(block)
                target.write(block)
    require(length == expected_length, "Downloaded cask length differs")
    require(value.hexdigest() == expected_sha, "Downloaded cask SHA-256 differs")


def verify_artifact(archive, receipt):
    artifact = receipt["artifact"]
    require(digest(archive) == artifact["sha256"], "Cask file SHA-256 differs")
    require(archive.stat().st_size == artifact["length"], "Cask file length differs")
    with tempfile.TemporaryDirectory(prefix="positionbar-cask-") as temporary:
        extracted = Path(temporary)
        run("ditto", "-x", "-k", archive, extracted)
        visible = [
            path
            for path in extracted.iterdir()
            if path.name not in ("__MACOSX", ".DS_Store")
        ]
        require(len(visible) == 1 and visible[0].name == artifact["appName"], "Cask App bundle changed")
        app = visible[0]
        require(app.is_dir(), "Cask artifact does not contain an App")
        require(not (app / "Contents/Frameworks/Sparkle.framework").exists(), "Cask App embeds Sparkle")
        require(
            not (app / "Contents/embedded.provisionprofile").exists(),
            "Cask App embeds an App Store profile",
        )
        run("codesign", "--verify", "--deep", "--strict", app)
        run(
            "codesign",
            "--verify",
            "--strict",
            "-R",
            f'=anchor apple generic and certificate leaf[field.1.2.840.113635.100.6.1.13] exists '
            f'and certificate leaf[subject.OU] = "{artifact["teamID"]}"',
            app,
        )
        run("xcrun", "stapler", "validate", app)
        run("spctl", "--assess", "--type", "execute", "--verbose=2", app)
        info = plistlib.loads((app / "Contents/Info.plist").read_bytes())
        require(info.get("CFBundleIdentifier") == artifact["bundleIdentifier"], "Cask bundle identifier differs")
        require(
            info.get("CFBundleShortVersionString") == receipt["version"]
            and info.get("CFBundleVersion") == str(receipt["build"]),
            "Cask App version/build differs from its receipt",
        )
        require(info.get("PBSourceRevision") == receipt["source"], "Cask App source revision differs")
        require(info.get("PBBuildID") == str(receipt["build"]), "Cask App Build ID differs")
        require(info.get("PBSourceDirty") is False, "Cask App contains dirty source")
        minimum = info.get("LSMinimumSystemVersion", "")
        parts = minimum.split(".")
        normalized = ".".join(parts + ["0"] * max(0, 3 - len(parts)))
        require(normalized == artifact["minimumSystemVersion"], "Cask minimum macOS differs")
        require(info.get("PBUpdatesEnabled") == "NO", "Cask App enables in-app updates")
        require(not info.get("SUFeedURL") and not info.get("SUPublicEDKey"), "Cask App configures Sparkle")
        entitlements = plistlib.loads(
            run("codesign", "-d", "--entitlements", ":-", app, capture=True).encode()
        )
        require(entitlements == artifact["entitlements"], "Cask App entitlements differ from its receipt")
        executable = app / "Contents/MacOS/PositionBar"
        architectures = sorted(
            run("lipo", "-archs", executable, capture=True).split(),
            key=("arm64", "x86_64").index,
        )
        require(architectures == artifact["architectures"], "Cask App architectures differ")
        return {
            "minimumSystemVersion": artifact["minimumSystemVersion"],
            "architectures": tuple(architectures),
            "appName": artifact["appName"],
        }


def homebrew_macos_symbol(version):
    symbol = run(
        "brew",
        "ruby",
        "-e",
        'require "macos_version"; puts MacOSVersion.new(ARGV.fetch(0)).to_sym',
        version,
        capture=True,
    ).strip()
    require(re.fullmatch(r"[a-z0-9_]+", symbol), "Unsupported Homebrew macOS version")
    return symbol


def render_cask(receipt, minimum_symbol):
    artifact = receipt["artifact"]
    architectures = tuple(artifact["architectures"])
    lines = [
        'cask "positionbar" do',
        f'  version "{receipt["version"]},{receipt["build"]}"',
        f'  sha256 "{artifact["sha256"]}"',
        "",
        f'  url "{artifact["url"]}"',
        '  name "PositionBar"',
        '  desc "Read-only multi-account position monitor"',
        '  homepage "https://positionbar.com/"',
        "",
        f"  depends_on macos: :{minimum_symbol}",
    ]
    if len(architectures) == 1:
        lines.append(f"  depends_on arch: :{architectures[0]}")
    lines.extend(["", f'  app "{artifact["appName"]}"', "end", ""])
    return "\n".join(lines)


def release_record(receipt):
    artifact = {
        key: receipt["artifact"][key]
        for key in (
            "url",
            "sha256",
            "length",
            "name",
            "appName",
            "bundleIdentifier",
            "architectures",
            "minimumSystemVersion",
            "teamID",
            "entitlements",
            "developerIDVerified",
            "notarizationStatus",
            "stapled",
            "gatekeeperVerified",
            "sparkleEmbedded",
        )
    }
    return {
        "schemaVersion": 1,
        "source": receipt["source"],
        "version": receipt["version"],
        "build": receipt["build"],
        "testFlight": receipt["testFlight"],
        "artifact": artifact,
        "tapRepository": "PositionBar/homebrew-tap",
    }


def cask_identity(contents):
    version = re.search(
        r'^  version "([0-9]+\.[0-9]+\.[0-9]+),([1-9][0-9]*)"$',
        contents,
        re.MULTILINE,
    )
    sha256 = re.search(r'^  sha256 "([a-f0-9]{64})"$', contents, re.MULTILINE)
    url = re.search(r'^  url "([^"]+)"$', contents, re.MULTILINE)
    require(
        version is not None and sha256 is not None and url is not None,
        "Existing cask identity is missing or invalid",
    )
    return (
        tuple(int(part) for part in version.group(1).split(".")) + (int(version.group(2)),),
        url.group(1),
        sha256.group(1),
    )


def write_candidate(path, contents):
    path = Path(path)
    if path.exists():
        current = path.read_text()
        if current == contents:
            return False
        current_version, current_url, current_sha = cask_identity(current)
        candidate_version, candidate_url, candidate_sha = cask_identity(contents)
        require(candidate_version >= current_version, "Refusing to downgrade the cask")
        if candidate_version == current_version:
            require(
                candidate_url == current_url and candidate_sha == current_sha,
                "The artifact URL or SHA-256 cannot change for an existing version",
            )
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(contents)
    temporary.replace(path)
    return True


def write_record(path, record):
    encoded = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    path = Path(path)
    if path.exists():
        current = json.loads(path.read_text())
        require(current.get("source") == record["source"], "Existing release record source differs")
        require(
            current.get("version") == record["version"] and current.get("build") == record["build"],
            "Existing release record version/build differs",
        )
        require(
            current.get("artifact", {}).get("sha256") == record["artifact"]["sha256"]
            and current.get("artifact", {}).get("url") == record["artifact"]["url"],
            "Existing release record artifact differs",
        )
        if path.read_text() == encoded:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(encoded)
    temporary.replace(path)
    return True


def run_brew_style(path):
    tap_parent = Path(run("brew", "--repository", capture=True).strip()) / "Library/Taps/positionbar"
    tap_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="homebrew-tap-check-", dir=tap_parent) as temporary:
        candidate = Path(temporary) / "Casks/positionbar.rb"
        candidate.parent.mkdir()
        shutil.copy2(path, candidate)
        run("brew", "style", "--cask", candidate)


def publication_git_state(cask_contents, record_contents, record_path):
    relative_record = str(Path(record_path).relative_to(ROOT))
    allowed = {"Casks/positionbar.rb", relative_record}
    status = run(
        "git",
        "-C",
        ROOT,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        capture=True,
    ).splitlines()
    require(all(line[3:] in allowed for line in status), "Tap worktree has changes outside the publication receipt")
    branch = run("git", "-C", ROOT, "branch", "--show-current", capture=True).strip()
    require(branch == "main", "Publish only from the tap main branch")
    run("git", "-C", ROOT, "fetch", "origin", "main")
    head = run("git", "-C", ROOT, "rev-parse", "HEAD", capture=True).strip()
    remote = run("git", "-C", ROOT, "rev-parse", "origin/main", capture=True).strip()
    if head == remote:
        return "current"
    ancestor = subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", remote, head],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    require(ancestor.returncode == 0, "Local tap main has diverged from origin/main")
    commits = int(run("git", "-C", ROOT, "rev-list", "--count", f"{remote}..{head}", capture=True))
    files = run("git", "-C", ROOT, "diff", "--name-only", f"{remote}..{head}", capture=True).split()
    require(
        commits == 1
        and set(files) == allowed
        and run("git", "-C", ROOT, "log", "-1", "--format=%s", "HEAD", capture=True).startswith(
            "Publish PositionBar cask to "
        ),
        "Unpushed tap commits are not a recoverable cask publication",
    )
    require(
        run("git", "-C", ROOT, "show", "HEAD:Casks/positionbar.rb", capture=True) == cask_contents
        and run("git", "-C", ROOT, "show", f"HEAD:{relative_record}", capture=True) == record_contents,
        "An unpublished cask commit differs from the prepared publication",
    )
    return "ahead"


def publish(receipt_path, execute=False):
    receipt = load_receipt(receipt_path)
    if not execute:
        return {
            "mode": "dry-run",
            "status": "not verified",
            "source": receipt["source"],
            "version": receipt["version"],
            "build": receipt["build"],
            "effect": "No download, Apple verification, commit, or push",
        }
    with tempfile.TemporaryDirectory(prefix="positionbar-download-") as temporary:
        archive = Path(temporary) / receipt["artifact"]["name"]
        download(
            receipt["artifact"]["url"],
            archive,
            receipt["artifact"]["sha256"],
            receipt["artifact"]["length"],
        )
        verified = verify_artifact(archive, receipt)
    minimum_symbol = homebrew_macos_symbol(verified["minimumSystemVersion"])
    contents = render_cask(receipt, minimum_symbol)
    record = release_record(receipt)
    record_path = RELEASES / f"positionbar-{receipt['version']}-{receipt['build']}.json"
    record_contents = json.dumps(record, ensure_ascii=False, indent=2) + "\n"
    state = publication_git_state(contents, record_contents, record_path)
    changed_cask = write_candidate(CASK, contents)
    changed_record = write_record(record_path, record)
    run_brew_style(CASK)
    needs_commit = bool(
        run(
            "git",
            "-C",
            ROOT,
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            "Casks/positionbar.rb",
            record_path,
            capture=True,
        ).strip()
    )
    if not needs_commit and state == "current":
        return {
            "status": "already published",
            "source": receipt["source"],
            "version": receipt["version"],
            "build": receipt["build"],
            "tapCommit": run("git", "-C", ROOT, "rev-parse", "HEAD", capture=True).strip(),
            "releaseRecord": str(record_path.relative_to(ROOT)),
        }
    if needs_commit:
        run("git", "-C", ROOT, "add", "Casks/positionbar.rb", record_path)
        run(
            "git",
            "-C",
            ROOT,
            "commit",
            "-m",
            f"Publish PositionBar cask to {receipt['version']} ({receipt['build']})",
        )
    commit = run("git", "-C", ROOT, "rev-parse", "HEAD", capture=True).strip()
    try:
        run("git", "-C", ROOT, "push", "origin", "HEAD:main")
    except subprocess.CalledProcessError as error:
        raise ValueError(
            f"Tap push failed after local commit {commit}; cask publication state is uncertain"
        ) from error
    try:
        remote = run("git", "-C", ROOT, "ls-remote", "origin", "refs/heads/main", capture=True).split()[0]
    except (subprocess.CalledProcessError, IndexError) as error:
        raise ValueError(
            f"Tap remote read-back failed after pushing {commit}; publication state is uncertain"
        ) from error
    require(remote == commit, "Tap main differs after push; publication state is uncertain")
    return {
        "status": "pushed",
        "source": receipt["source"],
        "version": receipt["version"],
        "build": receipt["build"],
        "tapCommit": commit,
        "releaseRecord": str(record_path.relative_to(ROOT)),
        "changed": changed_cask or changed_record,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("check", "publish"))
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--result", type=Path)
    args = parser.parse_args()
    if args.command == "check":
        receipt = load_receipt(args.receipt)
        with tempfile.TemporaryDirectory(prefix="positionbar-check-") as temporary:
            archive = Path(temporary) / receipt["artifact"]["name"]
            download(
                receipt["artifact"]["url"],
                archive,
                receipt["artifact"]["sha256"],
                receipt["artifact"]["length"],
            )
            facts = verify_artifact(archive, receipt)
        result = {
            "mode": "check",
            "status": "candidate only; not published",
            "source": receipt["source"],
            "version": receipt["version"],
            "build": receipt["build"],
            **facts,
        }
    else:
        result = publish(args.receipt, args.execute)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.result:
        temporary = args.result.with_suffix(args.result.suffix + ".tmp")
        temporary.parent.mkdir(parents=True, exist_ok=True)
        temporary.write_text(encoded)
        temporary.replace(args.result)
    print(encoded, end="")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
