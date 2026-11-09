#!/usr/bin/env python3
"""Resolve explicit release inputs and trusted same-tap recovery artifacts."""
import argparse
import json
import re
import subprocess
import sys

REPOSITORY = "PositionBar/homebrew-tap"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def github(endpoint):
    value = subprocess.run(["gh", "api", endpoint], capture_output=True, text=True)
    require(value.returncode == 0, "GitHub release input could not be verified")
    return json.loads(value.stdout)


def resolve_source(source, publishing):
    require(re.fullmatch(r"[0-9a-f]{40}", source), "Pass the full application source SHA")
    if publishing:
        current = github("repos/sorcererxw/positionbar/commits/main")
        require(current.get("sha") == source, "Publication must use the observed private source main SHA")
    return source


def recovery_artifact(run_id):
    require(re.fullmatch(r"[1-9][0-9]{0,19}", run_id), "Invalid recovery run ID")
    run = github(f"repos/{REPOSITORY}/actions/runs/{run_id}")
    require(run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("head_branch") == "main"
            and run.get("event") == "workflow_dispatch"
            and run.get("path") == ".github/workflows/release.yml",
            "Recovery must come from this tap's main paired-release workflow")
    artifacts = github(f"repos/{REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100")
    live = {item.get("name") for item in artifacts.get("artifacts", []) if not item.get("expired")}
    for name in ("homebrew-state", "testflight-state"):
        if name in live:
            return name
    raise ValueError("No retained checkpoint is available; do not repeat the TestFlight upload")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    source = sub.add_parser("source")
    source.add_argument("--sha", required=True)
    source.add_argument("--publish", action="store_true")
    restore = sub.add_parser("recovery")
    restore.add_argument("--run-id", required=True)
    args = parser.parse_args()
    if args.command == "source":
        print("sha=" + resolve_source(args.sha, args.publish))
    else:
        print("artifact=" + recovery_artifact(args.run_id))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(str(error) if isinstance(error, ValueError) else type(error).__name__, file=sys.stderr)
        sys.exit(1)
