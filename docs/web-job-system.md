# SourcePRISM durable job-system checkpoint

Recorded: 2026-10-11

## Agreed architecture

- Single Ubuntu host initially; laptop-first development.
- SQLite database on persistent local disk.
- One serialized report worker.
- Maximum 20 waiting jobs plus one running job.
- Cache-first report delivery and duplicate-request coalescing.
- Future migration to an always-on server after resource/load testing.

## Implemented foundation

job_store.py:
- Persistent job records and parameterized queries.
- WAL mode and short immediate write transactions.
- Atomic waiting-job admission.
- Coalescing of identical queued/running internal requests.
- Identity conflicts rejected.
- FIFO claiming and a database constraint permitting one running job.
- Guarded completed/failed transitions and sanitized error codes.

worker_lock.py:
- Cooperative Linux flock ownership.
- Persistent lock file; never unlink it.
- Lock ownership remains held until associated descriptors close.

worker_session.py:
- Shared lock path derived from the database path.
- Ownership held throughout the worker session.
- Interrupted running records become failed with WORKER_INTERRUPTED.
- Queued and completed records remain unchanged.
- No automatic requeue or replay during startup reconciliation.

## Test evidence

- 18 queue, ownership and reconciliation tests passed in 4.37 seconds.
- Complete regression suite: 177 passed in 15.47 seconds.
- Tests cover concurrent admission, duplicate coalescing, single claiming,
  ownership exclusion, process-death lock release, persistence,
  guarded transitions and conservative restart-state reconciliation.

## Internal boundary

The store accepts validated internal settings and a server-derived identity.
It is not a public validation or authorization interface.
Production request identity must include the applicable data, code,
toolchain/schema and presentation versions.
Deduplication must respect access policy.

All workers touching the same pipeline state must share ownership.
A different database must not be used to bypass pipeline serialization.

## Not yet implemented or verified

- Supervised rendering and descendant-process termination.
- Protection against orphan render processes.
- Atomic artifact publication and verification.
- Publication/database crash-window reconciliation.
- Completed-artifact cache lookup and permission checks.
- HTTP API, frontend binding and user-facing errors.
- Retention, expiration, disk budgets and rate limits.
- Production volumes, resource limits and deployment.
- Twenty-request end-to-end load rehearsal.

The tests establish the foundation, not production readiness.

## Subprocess supervision checkpoint

Recorded: 2026-10-11

Implemented:
- Trusted argument-list execution without shell interpretation.
- Non-interactive subprocess input.
- New process session/group for supervised commands.
- Explicit ownership descriptor passed to the direct child.
- Exclusive creation of private logs with mode 0600.
- Positive finite timeout and cleanup-grace validation.
- Group termination followed by forced termination where necessary.
- Cleanup of ordinary same-group descendants even after direct-child exit.
- Preservation of nonzero exit codes and explicit timeout status.

Evidence:
- 14 supervisor unit/integration tests passed in 3.26 seconds.
- Complete regression suite: 191 passed in 19.11 seconds.
- Descendant cleanup tested for timeout and successful parent exit.
- Direct-child ownership retention tested after parent descriptor closure.

Outstanding safety boundaries:
- Tests do not establish containment of descendants that create a new
  session or close the ownership descriptor after supervisor death.
- Worker-container lifecycle and forced-restart tests remain required.
- Do not enable automatic real-render recovery until that boundary is tested.
- Logs still need storage budgets/retention controls.
- The 300-second timeout is provisional.
- Real renderer integration and atomic artifact publication are pending.

## Report-bundle verification and HTML-only downloads

Recorded: 2026-10-11

Implemented verification:
- Required non-empty HTML and provenance artifacts.
- Effective settings match the validated internal request.
- Custom-report identifier and cache-key format checks.
- Symlink and non-regular-entry rejection.
- Explicit HTML href/src/poster reference checks.
- Local resource containment and existence checks.
- SHA-256 inventory of bundle files.

A real custom report exposed missing PDF downloads in both Quarto's
automatic alternate-format links and the shared navigation helper.
The custom path now explicitly declares HTML-only generation.
The publisher suppresses automatic format links in that mode, and the
shared R navigation omits unavailable PDF links.
Standard release PDF-link behavior is preserved by default.

Evidence:
- 13 synthetic bundle-verification tests passed.
- 6 HTML-only download regression tests passed in 1.19 seconds.
- Complete suite: 210 passed in 21.99 seconds.
- Fresh researcher HTML-only bundle passed real-output verification.
- Verified file count: 14.
- Experiment: results/web-download-fix-zbYvfd.
- Cache key:
  b4bf4ba52d1490d0541cef10d9fe354b212724084cf7514c622580c5d8104962
- Render duration was not supplied in the recorded output.

Limits:
- Explicit reference checks do not cover CSS URLs, JavaScript requests,
  srcset, fragment targets or external resource availability.
- This verifier does not independently recompute scientific results.
- Full standard-release rendering after the fix remains to be verified.
- Atomic publication and publication/database reconciliation are pending.
- Earlier cached HTML is not retroactively repaired.
