# SourcePRISM web contract — draft v1

Status: initial form scope and restricted-first deployment sequence approved by the project owner on 2026-10-11. Operational and public-launch decisions remain open.

## Initial scope

Local-only development using public reference data.
No patient-data collection, arbitrary JSON uploads, executable templates,
user-controlled paths, commands, or data-source URLs.

Staging and public-launch access policies remain undecided.
No DNS, Cloudflare or public deployment changes are authorized by this draft.

## Proposed web request

Required:
- audience: public, health_institution, or researcher.

Optional:
- years: two ordered integers defining the reporting window.

Omitted years inherit the selected audience preset.
The current presets use [2021, 2025].
The tested custom request uses [2022, 2025].

A supported reporting-window allowlist must be established through
data-coverage inspection and rendering tests before enabling overrides.
The schema's 1900–2200 bounds are not a data-availability guarantee.

Reject unknown request fields.
No free-text title or question overrides in the initial web version.

## Server-controlled stakeholder settings

Load a committed audience preset; do not accept a full stakeholder
configuration from the browser.

Keep the following server-controlled:
- id, title, question and presentation
- period_type and compare_by
- geography
- reference_year and index_base_year
- needs_roles and measures_preferred
- classes_in_main_comparison
- exclusion and sensitivity policies
- source priority and group source systems
- dimension filters and exclusion notes
- report sections

Initial geography: CHFL, matching the tested request.
Keep reference_year and index_base_year at the preset value of 2019.

Before allowing reporting-window overrides, review preset titles and
questions for hard-coded years. Any generated wording must match the
effective request without changing scientific interpretation.

Validate the resulting stakeholder configuration with the existing
pipeline validator. Do not weaken scientific checks to make a request pass.

Audience selection changes presentation, not the evidence or visibility
of major limitations.

## Proposed API and report routes

POST /api/reports
- Validate input and applicable access/queue limits.
- Persist a job before returning HTTP 202.
- Return a job ID and status URL.

GET /api/reports/{job_id}
- States: queued, running, completed, failed, expired.
- Return sanitized errors; no internal paths or raw subprocess logs.

GET /reports/{job_id}/
- Serve a completed responsive HTML report with intact relative assets.

GET /reports/{job_id}/downloads/{artifact}
- Serve only allowlisted, verified artifacts.
- Do not promise PDF support until the custom path is tested.

## Execution requirements

One serialized worker initially.
Durable job state.
Unique server-generated job workspaces and output directories.
No shell-interpolated user input.
Publish verified output before marking a job completed.
Define restart recovery and partial-output cleanup.

## Decisions required before implementation/deployment

- Approve or revise the minimal request fields.
- Establish supported reporting windows.
- Select durable job storage.
- Set measured/provisional limits and test them.
- Decide staging authentication.
- Decide public generation and viewing permissions.
- Decide sharing, retention, deletion and cache reuse policies.
- Resolve source licensing and required attribution.

## Approved initial scope and tested windows

Approved on 2026-10-11:
- Audience selection plus tested reporting-window choices only.
- Scientific settings remain server-controlled.
- Local-only development, then authenticated restricted staging.
- No public launch until permissions, retention and limits are agreed.

Initial window allowlist:
- [2021, 2025]
- [2022, 2025]

All three audience presets rendered successfully for both windows.
The adapter uses server-owned, window-consistent title/question wording.
Adapter-generated 2022–2025 requests rendered for all three audiences,
with matching effective provenance settings.

The approval does not settle queue/storage limits, retention, sharing,
staging authentication implementation, or public access policy.
