"""Run at most one queued report as PID 1 in a dedicated Linux container."""

import argparse
import json
import math
import os
import sys
from pathlib import Path

from job_store import JobStore
from job_worker import run_one
from worker_lock import WorkerAlreadyRunning

ROOT = Path(__file__).resolve().parents[2]


class LaunchContractError(ValueError):
    """The worker was not launched at its required containment boundary."""


def require_container_pid1():
    if sys.platform != "linux" or os.getpid() != 1:
        raise LaunchContractError(
            "Worker requires Linux PID 1 in a dedicated private container "
            "PID namespace; nested worker launches are unsupported."
        )


def positive_seconds(value):
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected positive finite seconds."
        ) from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected positive finite seconds.")
    return number


def positive_integer(value):
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Expected a positive integer."
        ) from exc
    if number < 1:
        raise argparse.ArgumentTypeError("Expected a positive integer.")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job-root", required=True)
    parser.add_argument("--data-root", default=str(ROOT / "data/reference"))
    parser.add_argument("--timeout", type=positive_seconds, default=300)
    parser.add_argument("--grace", type=positive_seconds, default=1)
    parser.add_argument("--max-queued", type=positive_integer, default=20)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        require_container_pid1()
    except LaunchContractError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    job_root = Path(args.job_root)
    if job_root.is_symlink():
        print("Job root cannot be a symlink.", file=sys.stderr)
        return 2
    job_root = job_root.resolve()
    data_root = Path(args.data_root).resolve()
    if not data_root.is_dir():
        print("Configured data root must be an existing directory.",
              file=sys.stderr)
        return 2

    store = JobStore(
        job_root / "state" / "jobs.sqlite3",
        max_queued=args.max_queued,
    )
    store.initialize()
    try:
        result = run_one(
            store,
            workspace_root=job_root / "private",
            published_root=job_root / "published",
            data_root=data_root,
            cache_root=job_root / "cache",
            cwd=ROOT,
            timeout=args.timeout,
            grace=args.grace,
        )
    except WorkerAlreadyRunning:
        print("Worker ownership is already held.", file=sys.stderr)
        return 75

    if result is None:
        print(json.dumps({"state": "idle"}))
        return 0

    print(json.dumps({
        "job_id": result["job_id"],
        "state": result["state"],
        "error_code": result["error_code"],
    }, sort_keys=True))
    return 0 if result["state"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
