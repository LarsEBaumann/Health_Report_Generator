"""Single-host durable job records; no rendering or HTTP handling."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path


class QueueFull(ValueError):
    """The configured waiting-job capacity has been reached."""


class InvalidTransition(ValueError):
    """The job is not in the required source state."""


class JobStore:
    def __init__(self, path, max_queued=20):
        if type(max_queued) is not int or max_queued < 1:
            raise ValueError("max_queued must be a positive integer.")
        self.path = Path(path)
        self.max_queued = max_queued

    def _connect(self):
        connection = sqlite3.connect(
            self.path, timeout=5.0, isolation_level=None
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    @contextmanager
    def _transaction(self):
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        """Call during controlled startup before accepting requests."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = self._connect()
        try:
            mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
            if mode.lower() != "wal":
                raise RuntimeError("Could not enable SQLite WAL mode.")
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL UNIQUE,
                    request_key TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'queued'
                        CHECK(state IN (
                            'queued', 'running', 'completed', 'failed', 'expired'
                        )),
                    created_at TEXT NOT NULL DEFAULT
                        (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    started_at TEXT,
                    finished_at TEXT,
                    error_code TEXT
                );
                CREATE UNIQUE INDEX IF NOT EXISTS active_request
                    ON jobs(request_key)
                    WHERE state IN ('queued', 'running');
                CREATE UNIQUE INDEX IF NOT EXISTS one_running
                    ON jobs(state) WHERE state = 'running';
            """)
        finally:
            connection.close()

    @staticmethod
    def _record(row):
        if row is None:
            return None
        result = dict(row)
        result["request"] = json.loads(result.pop("request_json"))
        return result

    def get(self, job_id):
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(row)
        finally:
            connection.close()

    def submit(self, request_key, request):
        """Accept internal validated settings and a server-derived identity."""
        if type(request_key) is not str or not request_key:
            raise ValueError("A non-empty internal request key is required.")
        if type(request) is not dict:
            raise ValueError("Internal request must be an object.")
        encoded = json.dumps(
            request, sort_keys=True, separators=(",", ":"), allow_nan=False
        )

        with self._transaction() as connection:
            row = connection.execute(
                """SELECT * FROM jobs
                   WHERE request_key = ? AND state IN ('queued', 'running')""",
                (request_key,),
            ).fetchone()
            if row is not None:
                if row["request_json"] != encoded:
                    raise ValueError("Request identity conflicts with settings.")
                return self._record(row), False

            queued = connection.execute(
                "SELECT COUNT(*) FROM jobs WHERE state = 'queued'"
            ).fetchone()[0]
            if queued >= self.max_queued:
                raise QueueFull("Waiting-job capacity reached.")

            job_id = uuid.uuid4().hex
            connection.execute(
                """INSERT INTO jobs(job_id, request_key, request_json)
                   VALUES (?, ?, ?)""",
                (job_id, request_key, encoded),
            )
            row = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
            ).fetchone()
            return self._record(row), True

    def claim_next(self):
        with self._transaction() as connection:
            if connection.execute(
                "SELECT 1 FROM jobs WHERE state = 'running'"
            ).fetchone():
                return None

            row = connection.execute(
                """SELECT * FROM jobs WHERE state = 'queued'
                   ORDER BY sequence LIMIT 1"""
            ).fetchone()
            if row is None:
                return None

            connection.execute(
                """UPDATE jobs SET state = 'running',
                   started_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE job_id = ? AND state = 'queued'""",
                (row["job_id"],),
            )
            updated = connection.execute(
                "SELECT * FROM jobs WHERE job_id = ?", (row["job_id"],)
            ).fetchone()
            return self._record(updated)

    def finish(self, job_id, state, error_code=None):
        """Worker calls completed only after verified atomic publication."""
        if state not in ("completed", "failed"):
            raise ValueError("Finish state must be completed or failed.")
        if state == "completed" and error_code is not None:
            raise ValueError("Completed jobs cannot have an error code.")
        if error_code is not None and (
            type(error_code) is not str
            or not error_code
            or len(error_code) > 64
            or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ_0123456789"
                   for c in error_code)
        ):
            raise ValueError("Use a short sanitized error code.")

        with self._transaction() as connection:
            cursor = connection.execute(
                """UPDATE jobs SET state = ?, error_code = ?,
                   finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE job_id = ? AND state = 'running'""",
                (state, error_code, job_id),
            )
            if cursor.rowcount != 1:
                raise InvalidTransition("Job is not running.")

    def fail_interrupted(self):
        """Internal startup operation; caller must hold worker ownership."""
        with self._transaction() as connection:
            rows = connection.execute(
                "SELECT job_id FROM jobs WHERE state = 'running'"
            ).fetchall()
            connection.execute(
                """UPDATE jobs SET state = 'failed',
                   error_code = 'WORKER_INTERRUPTED',
                   finished_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
                   WHERE state = 'running'"""
            )
            return [row["job_id"] for row in rows]
