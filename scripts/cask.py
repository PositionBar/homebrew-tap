#!/usr/bin/env python3
"""Check PositionBar release staging, generate the cask, and publish it locally."""

import argparse
import base64
import hashlib
import json
import plistlib
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import zipfile


SPARKLE_NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ROOT = Path(__file__).resolve().parents[1]
CASK = ROOT / "Casks/positionbar.rb"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def public_url(value, suffix):
    parsed = urlparse(value)
    require(
        parsed.scheme == "https"
        and parsed.hostname
        and (parsed.hostname == "positionbar.com" or parsed.hostname.endswith(".positionbar.com"))
        and not parsed.username
        and not parsed.password
        and not parsed.query
        and not parsed.fragment
        and parsed.port is None,
        "Expected a credential-free PositionBar HTTPS URL",
    )
    require(parsed.path.endswith(suffix), f"Expected a {suffix} URL")
    return parsed


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Public artifact URLs must not redirect")


def fetch(url):
    public_url(url, PurePosixPath(urlparse(url).path).suffix)
    with urllib.request.build_opener(NoRedirect).open(url, timeout=45) as response:
        require(response.status == 200, "Public artifact is unavailable")
        return response.read()


def run(*args, capture=False):
    result = subprocess.run(
        [str(argument) for argument in args],
        check=True,
        text=True,
        capture_output=capture,
    )
    return result.stdout if capture else ""


def load_source_contract(source_repo):
    scripts = Path(source_repo).resolve() / "scripts"
    for name in ("release.py", "releases.py"):
        require((scripts / name).is_file(), "Missing source release contract: " + name)
    sys.path.insert(0, str(scripts))
    try:
        for name in ("release", "releases"):
            sys.modules.pop(name, None)
        import release as release_contract
        import releases as releases_contract
    finally:
        sys.path.pop(0)
    require(
        Path(release_contract.__file__).resolve().parent == scripts
        and Path(releases_contract.__file__).resolve().parent == scripts,
        "Loaded release contract from the wrong source",
    )
    publishing = Path(source_repo).resolve() / "releases/publishing.example.json"
    team = json.loads(publishing.read_text()).get("teamID")
    require(isinstance(team, str) and re.fullmatch(r"[A-Z0-9]{10}", team), "Invalid source Team ID")
    return release_contract, releases_contract, team


def feed_entry(feed, release):
    raw = Path(feed).read_bytes()
    require(b"<!DOCTYPE" not in raw.upper(), "Appcast DTD is not allowed")
    entries = [
        entry
        for entry in ET.fromstring(raw).findall("./channel/item")
        if entry.findtext(f"{{{SPARKLE_NS}}}version") == str(release["build"])
    ]
    require(len(entries) == 1, "Appcast build is missing or duplicated")
    entry = entries[0]
    return entry


def inspect_stage(prepared, source_repo):
    prepared = Path(prepared).resolve()
    stage = prepared.parent
    manifest = json.loads(prepared.read_text())
    release = manifest["release"]
    artifact = release["artifact"]
    version = release["version"]
    build = release["build"]

    require(type(build) is int and build > 0, "Invalid release build")
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "Invalid marketing version")
    require(release.get("status") == "draft", "Prepared release must still be a draft")
    require(re.fullmatch(r"[a-f0-9]{64}", artifact.get("sha256", "")), "Invalid artifact SHA-256")
    require(type(artifact.get("length")) is int and artifact["length"] > 0, "Invalid artifact length")
    for name in ("edSignature",):
        try:
            signature = base64.b64decode(artifact.get(name, ""), validate=True)
        except ValueError:
            signature = b""
        require(len(signature) == 64, "Invalid Sparkle artifact signature")
    artifact_url = public_url(artifact.get("url", ""), ".zip")
    public_url(artifact.get("notesURL", ""), ".txt")
    public_url(manifest.get("feedURL", ""), ".xml")
    try:
        public_key = base64.b64decode(manifest.get("publicKey", ""), validate=True)
    except ValueError:
        public_key = b""
    require(len(public_key) == 32, "Invalid Sparkle public key")

    archive = stage / PurePosixPath(artifact_url.path).name
    notes = stage / PurePosixPath(urlparse(artifact["notesURL"]).path).name
    feed = stage / "appcast.xml"
    declared = manifest.get("files", {})
    require(
        set(declared) == {archive.name, notes.name, feed.name},
        "Prepared file manifest does not match release staging",
    )
    for name, expected in declared.items():
        require(Path(name).name == name, "Prepared file name is unsafe")
        path = stage / name
        require(path.is_file(), "Prepared file is missing: " + name)
        require(digest(path) == expected, "Prepared file SHA-256 differs: " + name)

    require(digest(archive) == artifact["sha256"], "Archive SHA-256 differs from prepared release")
    require(archive.stat().st_size == artifact["length"], "Archive size differs from prepared release")
    require(zipfile.is_zipfile(archive), "Prepared artifact is not a ZIP")
    with zipfile.ZipFile(archive) as bundle:
        names = bundle.namelist()
    for name in names:
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name, "Unsafe archive path")
    top_level = {
        PurePosixPath(name).parts[0]
        for name in names
        if name and PurePosixPath(name).parts[0] not in ("__MACOSX", ".DS_Store")
    }
    apps = [name for name in top_level if name.endswith(".app")]
    require(len(apps) == 1 and top_level == {apps[0]}, "Archive must contain exactly one top-level App")
    app_name = apps[0]

    entry = feed_entry(feed, release)
    enclosure = entry.find("enclosure")
    notes_link = entry.find(f"{{{SPARKLE_NS}}}releaseNotesLink")
    require(enclosure is not None and notes_link is not None and notes_link.text, "Appcast artifacts are missing")
    require(enclosure.get("url") == artifact["url"], "Appcast archive URL differs from prepared release")
    require(int(enclosure.get("length", "0")) == artifact["length"], "Appcast archive length differs")
    require(
        enclosure.get(f"{{{SPARKLE_NS}}}edSignature") == artifact["edSignature"],
        "Appcast archive signature differs from prepared release",
    )
    require(notes_link.text == artifact["notesURL"], "Appcast release notes URL differs")
    require(notes.stat().st_size == int(notes_link.get(f"{{{SPARKLE_NS}}}length", "0")), "Release notes length differs")

    with tempfile.TemporaryDirectory(prefix="positionbar-cask-") as temporary:
        extracted = Path(temporary)
        run("ditto", "-x", "-k", archive, extracted)
        visible = [
            path
            for path in extracted.iterdir()
            if path.name not in ("__MACOSX", ".DS_Store")
        ]
        require(len(visible) == 1 and visible[0].name == app_name, "Extracted App differs from archive")
        app = visible[0]
        info_path = app / "Contents/Info.plist"
        require(info_path.is_file(), "App Info.plist is missing")
        with info_path.open("rb") as source:
            info = plistlib.load(source)
        require(info.get("CFBundleIdentifier") == "com.positionbar.app", "Bundle identifier changed")
        require(
            info.get("CFBundleVersion") == str(build)
            and info.get("CFBundleShortVersionString") == version,
            "App version differs from prepared release",
        )
        minimum = info.get("LSMinimumSystemVersion")
        require(
            minimum and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", minimum),
            "App minimum system version is missing",
        )
        require(
            minimum == entry.findtext(f"{{{SPARKLE_NS}}}minimumSystemVersion"),
            "App and appcast minimum system versions differ",
        )
        require(info.get("SUPublicEDKey") == manifest["publicKey"], "App Sparkle public key differs")
        require(info.get("SUFeedURL") == manifest["feedURL"], "App Sparkle feed URL differs")
        require(
            info.get("PBUpdatesEnabled") == "YES"
            and info.get("SUVerifyUpdateBeforeExtraction") is True
            and info.get("SURequireSignedFeed") is True,
            "App update signature validation is not enabled",
        )
        require(
            info.get("SUEnableAutomaticChecks") is False
            and info.get("SUAutomaticallyUpdate") is False
            and info.get("SUEnableSystemProfiling") is False,
            "App update defaults changed",
        )
        executable = info.get("CFBundleExecutable")
        require(executable, "App executable is missing")
        executable_path = app / "Contents/MacOS" / executable
        require(executable_path.is_file(), "App executable file is missing")
        detected = tuple(
            sorted(
                run("lipo", "-archs", executable_path, capture=True).split(),
                key=("arm64", "x86_64").index,
            )
        )
        require(detected in (("arm64",), ("x86_64",), ("arm64", "x86_64")), "Unsupported App architectures")
        verify_authenticity(manifest, release, archive, notes, feed, app, minimum, source_repo)

    return {
        "manifest": manifest,
        "release": release,
        "app_name": app_name,
        "architectures": detected,
        "minimumSystemVersion": minimum,
    }


def verify_authenticity(manifest, release, archive, notes, feed, app, minimum, source_repo):
    release_contract, releases_contract, team = load_source_contract(source_repo)
    artifact = release["artifact"]
    with tempfile.TemporaryDirectory(prefix="positionbar-feed-") as scratch:
        release_contract.verify_feed(feed, manifest["publicKey"], scratch)
    metadata = releases_contract.verify_appcast(
        feed,
        release,
        artifact["url"],
        artifact["notesURL"],
        minimum,
    )
    require(
        metadata == {"edSignature": artifact["edSignature"], "length": artifact["length"]},
        "Appcast signature metadata differs from prepared release",
    )
    release_contract.verify_bytes(
        archive,
        manifest["publicKey"],
        artifact["edSignature"],
        artifact["length"],
    )
    entry = feed_entry(feed, release)
    notes_link = entry.find(f"{{{SPARKLE_NS}}}releaseNotesLink")
    release_contract.verify_notes(notes, manifest["publicKey"], notes_link)
    release_contract.verify_app(
        app,
        {"updates": {"publicEDKey": manifest["publicKey"], "feedURL": manifest["feedURL"]}},
        release,
        team,
    )


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


def candidate(prepared, source_repo):
    stage = inspect_stage(prepared, source_repo)
    stage["minimumSymbol"] = homebrew_macos_symbol(stage["minimumSystemVersion"])
    stage["contents"] = render_cask(
        stage["release"],
        stage["app_name"],
        stage["architectures"],
        stage["minimumSymbol"],
    )
    return stage


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


def verify_catalog_release(release, source_repo, catalog):
    release_contract, releases_contract, _ = load_source_contract(source_repo)
    del release_contract
    data = releases_contract.load(Path(catalog))
    published = releases_contract.release(data, release["build"])
    require(published["status"] == "published", "Release is not marked published in the source catalog")
    for field in ("version", "build", "publishedOn", "artifact"):
        require(published.get(field) == release.get(field), "Published catalog differs from prepared release")
    return published


def run_brew_style(path):
    tap_parent = Path(run("brew", "--repository", capture=True).strip()) / "Library/Taps/positionbar"
    tap_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="homebrew-tap-check-", dir=tap_parent) as temporary:
        candidate = Path(temporary) / "Casks/positionbar.rb"
        candidate.parent.mkdir()
        shutil.copy2(path, candidate)
        run("brew", "style", "--cask", candidate)


def publication_git_state(candidate_contents):
    status = run(
        "git",
        "-C",
        ROOT,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
        capture=True,
    ).splitlines()
    require(
        all(line[3:] == "Casks/positionbar.rb" for line in status),
        "Tap worktree has changes outside Casks/positionbar.rb",
    )
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
    subject = run("git", "-C", ROOT, "log", "-1", "--format=%s", "HEAD", capture=True).strip()
    require(
        commits == 1
        and files == ["Casks/positionbar.rb"]
        and subject.startswith("Update PositionBar cask to "),
        "Unpushed tap commits are not a recoverable cask publication",
    )
    pending = run("git", "-C", ROOT, "show", "HEAD:Casks/positionbar.rb", capture=True)
    require(
        pending == candidate_contents,
        "An unpublished cask commit differs from the prepared candidate; finish or reconcile it first",
    )
    return "ahead"


def publish(prepared, execute=False, source_repo=None, catalog=None):
    if not execute:
        return {
            "mode": "dry-run",
            "operation": "publish",
            "status": "not run",
            "prepared": str(Path(prepared)),
            "effect": "No verification, network access, Git commit, or push",
        }
    require(source_repo is not None, "--positionbar-repo is required")
    source_repo = Path(source_repo).resolve()
    stage = candidate(prepared, source_repo)
    release = stage["release"]
    catalog = Path(catalog) if catalog else source_repo / "releases/catalog.json"
    verify_catalog_release(release, source_repo, catalog)

    public_sha = hashlib.sha256(fetch(release["artifact"]["url"])).hexdigest()
    require(public_sha == release["artifact"]["sha256"], "Public artifact SHA-256 differs from prepared release")

    state = publication_git_state(stage["contents"])
    write_candidate(CASK, stage["contents"])
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
            capture=True,
        ).strip()
    )
    if not needs_commit and state == "current":
        return {
            "mode": "published",
            "status": "already published",
            "version": release["version"],
            "build": release["build"],
            "commit": run("git", "-C", ROOT, "rev-parse", "HEAD", capture=True).strip(),
            "artifact": release["artifact"]["url"],
        }

    if needs_commit:
        run("git", "-C", ROOT, "add", "Casks/positionbar.rb")
        run(
            "git",
            "-C",
            ROOT,
            "commit",
            "-m",
            f"Update PositionBar cask to {release['version']} ({release['build']})",
        )
    commit = run("git", "-C", ROOT, "rev-parse", "HEAD", capture=True).strip()
    try:
        run("git", "-C", ROOT, "push", "origin", "HEAD:main")
    except subprocess.CalledProcessError as error:
        raise ValueError(
            f"Push failed after local commit {commit}; publication state is uncertain. "
            "Retry the same publish command after checking origin/main."
        ) from error
    try:
        remote = run("git", "-C", ROOT, "ls-remote", "origin", "refs/heads/main", capture=True).split()[0]
    except (subprocess.CalledProcessError, IndexError) as error:
        raise ValueError(
            f"Remote read-back failed after pushing {commit}; publication state is uncertain."
        ) from error
    require(remote == commit, "Remote tap main differs after push; publication state is uncertain")
    return {
        "mode": "published",
        "status": "pushed",
        "version": release["version"],
        "build": release["build"],
        "commit": commit,
        "artifact": release["artifact"]["url"],
    }


def render_cask(release, app_name, architectures, minimum_symbol):
    version = release["version"]
    build = release["build"]
    artifact = release["artifact"]
    require(re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version), "Invalid marketing version")
    require(type(build) is int and build > 0, "Invalid build")
    require(re.fullmatch(r"[a-f0-9]{64}", artifact["sha256"]), "Invalid artifact SHA-256")
    require(
        re.fullmatch(r"[A-Za-z0-9 ._+-]+\.app", app_name),
        "Unsafe app bundle name",
    )
    require(architectures in (("arm64",), ("x86_64",), ("arm64", "x86_64")), "Unsupported architectures")

    lines = [
        'cask "positionbar" do',
        f'  version "{version},{build}"',
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
    lines.extend(["", f'  app "{app_name}"', "end", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    for name in ("check", "generate", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--prepared", type=Path, required=True)
        command.add_argument("--positionbar-repo", type=Path)
        if name == "generate":
            command.add_argument("--output", type=Path, default=CASK)
        if name == "publish":
            command.add_argument("--catalog", type=Path)
            command.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    if args.command == "publish" and not args.execute:
        result = publish(args.prepared)
    else:
        require(args.positionbar_repo is not None, "--positionbar-repo is required")
        if args.command == "publish":
            result = publish(
                args.prepared,
                execute=True,
                source_repo=args.positionbar_repo,
                catalog=args.catalog,
            )
        else:
            stage = candidate(args.prepared, args.positionbar_repo)
            if args.command == "check":
                result = {
                    "mode": "check",
                    "status": "candidate only; not published",
                    "version": stage["release"]["version"],
                    "build": stage["release"]["build"],
                    "artifact": stage["release"]["artifact"]["url"],
                    "sha256": stage["release"]["artifact"]["sha256"],
                    "app": stage["app_name"],
                    "architectures": list(stage["architectures"]),
                    "minimumSystemVersion": stage["minimumSystemVersion"],
                }
            else:
                changed = write_candidate(args.output, stage["contents"])
                result = {
                    "mode": "generate",
                    "status": "candidate written; not published",
                    "output": str(args.output.resolve()),
                    "changed": changed,
                }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
