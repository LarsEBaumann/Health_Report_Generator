#!/usr/bin/env python3
"""One entry point for everything in this repository, on Windows, Linux and macOS.

    python run.py              Build the reports (add --open to open them)
    python run.py web          Open the report builder page (pick diseases, build locally)
    python run.py app          Start the Marimo interface (GitHub request flow)
    python run.py test         Run the tests
    python run.py release      Build the full three-audience release (needs Docker)
    python run.py clean        Delete everything the build produced

Every task runs through `uv run`, which creates and updates the single Python environment
on its own: there is no setup step and nothing to activate. This script itself uses only
the standard library, so any Python 3 can start it.
"""
import argparse
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LANDING = ROOT / "results" / "site" / "index.html"
BUILD_ARTIFACTS = ["results", ".snakemake"]

UV_HINT = "Install it from https://docs.astral.sh/uv/getting-started/installation/"
QUARTO_HINT = "Install it from https://quarto.org/docs/get-started/"


def need(program, hint):
    """Stop with a readable message instead of a traceback or a cryptic OSError."""
    found = shutil.which(program)
    if not found:
        sys.exit(f"\nMissing: {program}\n  {hint}\n")
    return found


def run(*command, **env_overrides):
    """Run a command in the repository root and stop the script if it fails."""
    env = None
    if env_overrides:
        env = {**os.environ, **env_overrides}
    print("+ " + " ".join(str(c) for c in command), flush=True)
    completed = subprocess.run([str(c) for c in command], cwd=ROOT, env=env)
    if completed.returncode != 0:
        sys.exit(completed.returncode)


def uv(*arguments):
    """`uv run --quiet` keeps uv's own environment chatter out of the build log."""
    run("uv", "run", "--quiet", *arguments)


def task_report(args):
    # Quarto renders the documents; everything else is Python.
    need("quarto", QUARTO_HINT)
    print("Building reports (the first run takes a few minutes)...")
    uv("snakemake", "quarto", "--cores", args.cores)
    print(f"\nDone: {LANDING}")
    print("Open that file, or run `python run.py web` to read the reports in the explorer.")
    if args.open:
        webbrowser.open(LANDING.as_uri())


def task_app(args):
    # The interface prefers a bundle built here, so it works with no GitHub account. Only
    # the analysis tables are needed, which is the part of the build that does not use R.
    if not any((ROOT / "results" / "reports").glob("*/data/series.csv")):
        need("quarto", QUARTO_HINT)
        print("Preparing the local dataset list (first run only)...")
        uv("snakemake", "tables", "--cores", args.cores)
    print(f"Starting the web interface on http://127.0.0.1:{args.port}")
    print("It builds reports locally; no GitHub account or token is needed.")
    print("Press Ctrl+C to stop.")
    uv("marimo", "run", "frontend/ui.py", "--headless", "--host", "127.0.0.1", "--port", args.port)


def task_web(args):
    """The report builder page: choose an audience and diseases, build locally."""
    need("quarto", QUARTO_HINT)
    if not any((ROOT / "results" / "reports").glob("*/data/series.csv")):
        print("Preparing the local dataset list (first run only)...")
        uv("snakemake", "tables", "--cores", args.cores)
    address = f"http://127.0.0.1:{args.port}"
    print(f"Report builder on {address}")
    print("Everything is built on this machine; no GitHub account or token is needed.")
    print("Press Ctrl+C to stop.")
    if args.open:
        # The server blocks, so the browser is opened a moment after it starts.
        threading.Timer(1.5, webbrowser.open, args=[address]).start()
    uv("uvicorn", "frontend.web.app:app", "--host", "127.0.0.1", "--port", args.port,
       "--log-level", "warning")


def task_test(args):
    # Four failures are expected on Windows: the tests read UTF-8 files without an
    # explicit encoding, and one shells out to bash. They pass in the container.
    uv("pytest", "-q")


def task_release(args):
    # The full release also builds PDFs and Shiny apps, which need R and TeX. The
    # container carries both; a bare host usually does not.
    if shutil.which("docker"):
        print("Building the full release in Docker...")
        ids = {}
        if hasattr(os, "getuid"):  # POSIX only; the image maps file ownership to these.
            ids = {"LOCAL_UID": str(os.getuid()), "LOCAL_GID": str(os.getgid())}
        run("docker", "compose", "build", "report", **ids)
        run("docker", "compose", "run", "--rm", "report",
            "snakemake", "--cores", args.cores, **ids)
        return
    print(
        "\nDocker was not found, so this falls back to a native build.\n"
        "That needs R and TeX as well; without them the PDF and Shiny steps fail.\n"
        "For reports that need neither, use: python run.py\n"
    )
    need("quarto", QUARTO_HINT)
    uv("snakemake", "--cores", args.cores)


def task_clean(args):
    for name in BUILD_ARTIFACTS:
        target = ROOT / name
        if target.exists():
            shutil.rmtree(target)
            print(f"Removed {name}")
    print("Clean. Rebuild with: python run.py")


TASKS = {
    "report": task_report,
    "web": task_web,
    "app": task_app,
    "test": task_test,
    "release": task_release,
    "clean": task_clean,
}


def main():
    parser = argparse.ArgumentParser(
        prog="python run.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task", nargs="?", default="report", choices=sorted(TASKS),
                        help="what to do (default: report)")
    parser.add_argument("--cores", default="2", help="parallel build jobs (default: 2)")
    parser.add_argument("--port", default="2718", help="web interface port (default: 2718)")
    parser.add_argument("--open", action="store_true",
                        help="also open the result in a browser (nothing opens by default)")
    # Accepted so earlier commands keep working; not opening is now the default.
    parser.add_argument("--no-open", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    # uv manages the environment and the Python version, so it is the only prerequisite.
    need("uv", UV_HINT)
    TASKS[args.task](args)


if __name__ == "__main__":
    main()
