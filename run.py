#!/usr/bin/env python3
"""Run the full reproducible report release in the locked Docker environment.

Usage:
    python run.py release --cores 2
    python run.py --cores 2          # release is the default

The command builds (or reuses) the Docker image defined by Dockerfile.request,
then runs this branch's Snakefile inside it.  Results are written to ./results.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
COMPOSE = ROOT / "compose.full-report.yml"


def run(command: list[str], env: dict[str, str]) -> None:
    print("+ " + " ".join(command), flush=True)
    result = subprocess.run(command, cwd=ROOT, env=env)
    if result.returncode:
        raise SystemExit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="release", choices=["release"])
    parser.add_argument("--cores", default="2", help="Snakemake cores (default: 2)")
    args = parser.parse_args()
    if not str(args.cores).isdigit() or int(args.cores) < 1:
        parser.error("--cores must be a positive whole number")
    if not shutil.which("docker"):
        raise SystemExit("Docker Desktop must be installed and running. See marimo-ui/README.md.")

    env = os.environ.copy()
    if hasattr(os, "getuid"):
        env.setdefault("LOCAL_UID", str(os.getuid()))
        env.setdefault("LOCAL_GID", str(os.getgid()))
    compose = ["docker", "compose", "-f", str(COMPOSE)]
    run([*compose, "build", "full-report"], env)
    run([*compose, "run", "--rm", "full-report", "snakemake", "--cores", str(args.cores)], env)


if __name__ == "__main__":
    main()
