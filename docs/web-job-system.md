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

## Atomic publication and restart reconciliation

Recorded: 2026-10-11

Implemented:
- Verify source bundle before copying.
- Copy into private staging on the publication filesystem.
- Verify copied inventory against the source.
- Write a versioned publication manifest.
- Synchronize files/directories and rename into the job destination.
- Serialize cooperating publishers using a persistent root lock.
- Reject conflicting existing destinations.
- Verify repeat publication without overwriting matching output.
- Independently validate published identity and file hashes.

Startup reconciliation under worker ownership:
- Valid published running job: restore completed without rerendering.
- No published output: failed / WORKER_INTERRUPTED.
- Invalid published output: failed / PUBLICATION_INVALID.
- Preserve queued jobs, completed jobs and diagnostic artifacts.

Evidence:
- 10 initial publication tests passed.
- Real researcher report publication and repeat publication passed.
- Reopened SQLite state retained completion.
- Published inventory matched all 14 source report files.
- Real experiment: results/web-publication-yGT7c0.
- 20 publication/recovery/session tests passed in 2.10 seconds.
- Complete regression suite: 224 passed in 21.99 seconds.
- Recovery tested without the original private source workspace.

Limitations:
- Restart tests simulate interrupted database state; they do not constitute
  a forced crash of the complete rendering/container stack.
- Publication requires trusted stable local storage and cooperative locking.
- The filesystem and SQLite are not one combined atomic transaction;
  the verified manifest enables reconciliation of the publication gap.
- Untrusted clients must never choose internal identities or paths.
- Staging, locks, database files and publication metadata are not public routes.
- Real worker integration, container crash containment, resource budgets,
  artifact access/retention and end-to-end load rehearsal remain pending.

## Single-job worker integration

Recorded: 2026-10-11

Implemented:
- Acquire worker ownership and reconcile interrupted state.
- Claim at most one queued job per operation.
- Create a fresh private job workspace and request file.
- Invoke the renderer through the existing process supervisor.
- Pass the worker ownership descriptor to the supervised process.
- Publish verified successful output before persisting completion.
- Persist sanitized render timeout, render failure, invalid report
  and publication conflict codes.
- Leave unexpected infrastructure errors recoverable through startup
  reconciliation rather than misclassifying published output as failed.

Evidence:
- Synthetic renderer uses the actual supervisor and publication code.
- Successful publication and completion persisted after database reopening.
- Renderer failure, timeout and invalid output were tested.
- Empty queue did not launch a renderer.
- Processing one job preserved the next queued job.
- Simulated completion-persistence failure left verified publication
  recoverable as completed.
- Invalid timeout configuration did not claim a queued job.
- 28 worker/publication/recovery/session tests passed in 4.46 seconds.
- Complete regression suite: 232 passed in 24.76 seconds.

Limitations:
- This increment exposes an internal Python operation, not a worker CLI
  or a persistent service loop.
- Renderer overrides and filesystem paths are trusted internal
  configuration and must not come from client requests.
- Synthetic worker tests do not establish successful queued Quarto
  rendering or real worker-container crash containment.
- Resource budgets, log-size limits, artifact access/retention and
  end-to-end load rehearsal remain pending.

## Real queued-report experiment

Recorded: 2026-10-11
Implementation checkpoint: 1468ebc

Experiment:
- Workspace: results/web-worker-gofAxq
- Request: existing public stakeholder configuration, validated through
  analyse.load_config.
- Job ID: eb162ed2c4904758896a37ad159315dc
- Request key:
  fdd6d59ce632c4755f595b5f4bbf90475b363347fe9ea87a5f0a533ec801ba86
- Snapshot ID:
  d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee
- Fresh experiment-local database, private workspace, publication root
  and report cache.

Verified:
- Duplicate submission while queued reused the active job.
- run_one invoked the actual custom_report.py renderer through the
  process supervisor.
- Renderer log confirmed a report-cache miss.
- Rendered cache identity matched the submitted request key.
- Published manifest and all 14 report-file hashes verified.
- Completed state persisted after reopening SQLite.
- An empty-queue operation did not rerender, alter the completed record,
  change the publication manifest or modify the render log.
- Working tree remained clean after the experiment.

Artifacts:
- Database:
  results/web-worker-gofAxq/state/jobs.sqlite3
- Published report:
  results/web-worker-gofAxq/published/eb162ed2c4904758896a37ad159315dc
- Private render log:
  results/web-worker-gofAxq/private/eb162ed2c4904758896a37ad159315dc/render.log

Limitations:
- This demonstrates successful real queued rendering, not forced
  worker-container crash containment.
- Identity equality was checked after rendering; snapshot pinning
  and pre-completion identity enforcement remain separate work.
- No HTTP interface, persistent worker service, resource-budget
  enforcement or artifact-access policy was established by this experiment.

## Whole-container crash rehearsal

Recorded: 2026-10-11
Implementation checkpoint: 1468ebc

Experiment:
- Workspace: results/web-crash-sd25Hl
- Dedicated container: health-report-crash-web-crash-sd25Hl
- Synthetic renderer with a sleeping descendant.
- Fresh experiment-local SQLite database and private workspace.
- One running job and one waiting job.
- Only the dedicated experiment container received SIGKILL.
- Container exit code reported by docker wait: 137.

Verified:
- Pre-termination process listing showed the worker, renderer and
  descendant running in the dedicated container.
- A second container could not acquire worker ownership or reconcile
  the active running job.
- After whole-container termination, a new container acquired ownership
  against the same persisted database and filesystem.
- The interrupted job became failed / WORKER_INTERRUPTED.
- The waiting job remained queued.
- No report was published for the interrupted job.
- Repeated reconciliation left the terminal record unchanged.
- Working tree remained clean after the rehearsal.

Retained evidence:
- Database: results/web-crash-sd25Hl/state/jobs.sqlite3
- Job identities: results/web-crash-sd25Hl/jobs.json
- Synthetic scripts and readiness/PID markers in the experiment workspace.
- Stopped dedicated container retained for inspection.

Limitations:
- This tests whole-container termination during synthetic rendering.
- It does not test worker-process-only death with a surviving renderer.
- It does not test a real Quarto render under forced termination.
- It does not inject termination between publication and SQLite completion.
- Inherited descriptors were deliberately retained by the synthetic
  renderer and descendant; this is not evidence that every real
  rendering descendant retains the worker descriptor.

## Worker-process-only death rehearsal

Recorded: 2026-10-11
Implementation checkpoint: 1468ebc

Experiment:
- Workspace: results/web-parent-death-VI0wdB
- Guardian remained alive inside the experiment container.
- Synthetic renderer deliberately passed inherited descriptors to
  its sleeping descendant.
- Fresh database with one running job and one waiting job.
- Worker, renderer and descendant were terminated separately.

Verified:
- Worker-only death left the renderer and descendant alive.
- Surviving renderer tree prevented replacement-worker reconciliation.
- After renderer termination, the surviving descendant still retained
  worker ownership and prevented reconciliation.
- Ownership became available after the final holder stopped.
- Interrupted job became failed / WORKER_INTERRUPTED.
- Waiting job remained queued.
- No report was published.
- Repeated reconciliation left the terminal record unchanged.
- Working tree remained clean after the rehearsal.

Retained evidence:
- Database: results/web-parent-death-VI0wdB/state/jobs.sqlite3
- Job identities: results/web-parent-death-VI0wdB/jobs.json
- Rehearsal, renderer and PID markers in the experiment workspace.

Limitations:
- Descriptor inheritance was deliberately enabled in the synthetic tree.
- This does not establish descriptor retention throughout the real
  Snakemake, Quarto or R process tree.
- The actual renderer launch path still requires a separate containment
  decision before deployment.
- Forced termination after publication but before SQLite completion
  remains a separate experiment.

## Publication-completion gap crash rehearsal

Recorded: 2026-10-11
Implementation checkpoint: 1468ebc

Experiment:
- Workspace: results/web-publication-gap-jYlw3t
- Job ID: 3712202d75c843acaa0ac51be4df1ce1
- Actual run_one operation with a synthetic valid four-file report.
- Experiment-only JobStore subclass paused before persisting completed,
  after successful publication returned.
- Guardian sent SIGKILL to the paused worker.
- Original private workspace was renamed to private-preserved,
  retaining evidence but making its original path unavailable.

Verified:
- Published bundle passed verification while database state was running.
- Paused worker retained ownership and blocked reconciliation.
- SIGKILL prevented the completion update.
- Restart reconciliation restored completed from the published bundle
  without the original private workspace.
- Published report files and publication manifest retained their hashes,
  sizes and modification times.
- Waiting job record remained unchanged.
- Repeated reconciliation was idempotent.
- Recovered completion persisted after database reopening.
- Working tree remained clean after the rehearsal.

Retained evidence:
- Database:
  results/web-publication-gap-jYlw3t/state/jobs.sqlite3
- Published bundle:
  results/web-publication-gap-jYlw3t/published/3712202d75c843acaa0ac51be4df1ce1
- Pre-crash inventory:
  results/web-publication-gap-jYlw3t/published-before.json
- Original private workspace:
  results/web-publication-gap-jYlw3t/private-preserved
- Rehearsal scripts, job identities and completion-pause marker
  retained in the experiment workspace.

Limitations:
- Termination occurred at a controlled post-publication,
  pre-completion-persistence boundary.
- This does not test arbitrary termination during copying, synchronization
  or rename, or host power loss.
- Synthetic report generation does not establish real renderer-tree
  containment.
- Resource limits, identity enforcement before completion, artifact access
  and retention, and persistent service integration remain pending.

## Rendered identity enforcement

Recorded: 2026-10-11

Publication contract:
- Publication request_key must be a 64-character lowercase hexadecimal
  renderer-derived identity.
- Before staging or publication, the verified source bundle cache_key
  must equal the queued request_key.
- Existing publication verification requires equality between the
  queued request_key, manifest cache_key and verified rendered cache_key.
- A manifest request_key matching the job cannot conceal a mismatched
  rendered identity.

Worker and recovery behavior:
- Source identity mismatch is rejected before publication.
- Worker records failed / PUBLICATION_INVALID through existing handling.
- Restart reconciliation does not restore completed for a publication
  with mismatched rendered identity.
- Invalid published artifacts remain available for diagnosis.

Evidence:
- Successful synthetic publication fixtures use matching identities.
- Source mismatch was rejected without creating the publication root.
- Invalid publication request-key formats were rejected.
- A matching declared manifest request identity did not conceal a
  different rendered cache identity.
- Worker mismatch failed without publishing and retained private output.
- Recovery mismatch failed without modifying the published artifacts.
- 36 focused tests passed in 5.19 seconds.
- Complete regression suite: 240 passed in 24.66 seconds.

Compatibility and limitations:
- JobStore remains a generic internal queue and accepts arbitrary keys;
  jobs reaching report publication must use renderer-derived keys.
- Earlier synthetic experiment scripts using arbitrary publication keys
  require fixture updates before rerunning.
- Earlier passing experiments remain historical evidence for their
  recorded implementation checkpoints.
- Identity enforcement detects drift; it does not pin the original
  data snapshot or toolchain.
- Effective custom report ID prefix consistency is not tightened
  by this increment.
- Successful real queued rendering under this stricter publication
  contract remains to be rerun.
- Real renderer-tree containment remains a deployment requirement.

## Real queued rendering with enforced identity

Recorded: 2026-10-11
Implementation checkpoint: b5a9140

Experiment:
- Workspace: results/web-worker-apua55
- Request: existing public stakeholder configuration, validated through
  analyse.load_config.
- Job ID: c97084708ad2495dba40218f6e1355ca
- Request key:
  090520500c27f9ff479c7b2126e03861eba155b2f24f80372ffb55444f0f0cc9
- Snapshot ID:
  d0709708a8057815801497701bfaa145017979f1ecace4508ae46237438573ee
- Fresh experiment-local database, private workspace, publication root
  and report cache.
- Reran the original real queued-report experiment without changing
  its request-key derivation or verification logic.

Verified:
- Duplicate queued submission reused the active job.
- Actual custom_report.py renderer completed through the supervisor.
- Renderer log confirmed a fresh report-cache miss.
- Rendered cache identity matched the queued request identity.
- Publication accepted the real output under the enforced identity contract.
- Published manifest and all 14 report-file hashes verified.
- Completed state persisted after reopening SQLite.
- Empty-queue operation did not rerender or alter completed output.
- Working tree remained clean after the experiment.

Retained evidence:
- Database:
  results/web-worker-apua55/state/jobs.sqlite3
- Published report:
  results/web-worker-apua55/published/c97084708ad2495dba40218f6e1355ca
- Private render log:
  results/web-worker-apua55/private/c97084708ad2495dba40218f6e1355ca/render.log

Status:
- Successful real queued rendering under the stricter identity contract
  is now verified, superseding the earlier pending-rerun note.
- Synthetic crash experiments recorded before b5a9140 remain historical
  evidence for their recorded implementation checkpoints.
- Identity enforcement detects drift but does not pin the original snapshot.
- Real renderer-tree containment, resource limits, artifact access and
  retention, and persistent worker service integration remain pending.

## Publication-gap recovery with enforced identity

Recorded: 2026-10-11
Implementation checkpoint: b5a9140
Documentation checkpoint at experiment start: 2a06428

Experiment:
- Workspace: results/web-publication-gap-identity-jZkUcF
- Job ID: 3df05119e1e14d96821ba620e9b435e2
- Copied the preserved publication-gap rehearsal into a fresh workspace.
- Running job used the synthetic renderer's matching cache identity:
  64 lowercase hexadecimal 'a' characters.
- Waiting job used a separate identity and was not rendered.
- Actual run_one operation used a synthetic valid four-file report.
- Experiment-only store subclass paused before persisting completed,
  after verified publication returned.
- Guardian sent SIGKILL to the paused worker.
- Original private workspace was preserved under a different name.

Verified:
- Publication succeeded under the enforced identity contract while
  database state remained running.
- Paused worker retained ownership and blocked premature reconciliation.
- SIGKILL prevented completion persistence.
- Restart restored completed from the published bundle without the
  original private workspace.
- All published files, including the publication manifest, retained
  their hashes, sizes and modification times.
- Waiting job record remained unchanged.
- Recovery was idempotent.
- Recovered completion persisted after database reopening.
- Working tree remained clean after the rehearsal.

Retained evidence:
- Database:
  results/web-publication-gap-identity-jZkUcF/state/jobs.sqlite3
- Published bundle:
  results/web-publication-gap-identity-jZkUcF/published/3df05119e1e14d96821ba620e9b435e2
- Pre-crash inventory, preserved private workspace, rehearsal scripts,
  job identities and completion-pause marker remain in the workspace.

Limitations:
- Synthetic keys match rendered provenance but are not derived from
  real snapshot, code and toolchain components in this rehearsal.
- Successful real renderer-derived identity was verified separately
  in results/web-worker-apua55.
- Termination targets a controlled post-publication,
  pre-completion-persistence boundary.
- Arbitrary publication interruption, host power loss, real renderer-tree
  containment and resource-budget enforcement remain separate work.

## PID-1 single-job container entry point

Recorded: 2026-10-11

Implemented:
- worker_once.py processes at most one queued job through run_one.
- Requires Linux and PID 1 before initializing or claiming jobs.
- Validates positive finite timeout/grace and positive queue capacity.
- Rejects a symlink job root and a missing data directory.
- Uses configured job-root directories for state, private workspaces,
  publications and cache.
- Does not expose a renderer override.
- Outputs only job ID, state and sanitized error code, or idle state.
- Returns 0 for idle/completed, 1 for a failed job, 2 for configuration
  or launch-contract rejection, and 75 for competing worker ownership.
- Unexpected infrastructure exceptions propagate rather than being
  misclassified as terminal report failures.

Launch contract:
- Run directly as PID 1 in a dedicated private container PID namespace.
- Do not launch beneath a surviving guardian or through docker exec.
- Do not use host/shared PID mode.
- HTTP/UI processes must be separate from the worker container.
- Paths and numeric configuration are trusted operator settings.
- PID 1 validation is a necessary check, not proof of all container settings.

Evidence:
- Report-service runtime probe showed Python PID 1, parent PID 0.
- Nested/non-PID-1 launch rejected before database creation.
- Platform gate, argument validation, directory validation, idle handling,
  allowlisted output and competing ownership were tested.
- Unexpected infrastructure failure propagation was tested.
- 31 entry-point/worker/session tests passed in 4.16 seconds.
- Complete regression suite: 256 passed in 24.84 seconds.

Limitations:
- Entry-point tests mock the launch gate where necessary to test CLI behavior.
- Live rendering and forced termination through this entry point
  remain separate verification gates.
- No persistent loop, automatic restart policy, HTTP integration,
  resource-budget enforcement or retention policy is implemented here.
