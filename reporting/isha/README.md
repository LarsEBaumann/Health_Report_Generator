# Isha report templates

This directory preserves the reports delivered from the `dev_isha` branch without
editing their QMD source. The request workflow uses
`scripts/health_pipeline/isha_report_adapter.py` to stage a selected slice of the
verified prepared data in the layout those documents expect.

Audience mapping is deliberately explicit:

| Request audience | Template |
|---|---|
| `researcher` | `source/reports/researcher.qmd` |
| `health_institution` | `source/reports/public_health.qmd` |
| `public` | existing simple request-report template |

The staged runtime copy of `helpers.py` receives a disease registry derived from
the validated request. The preserved source QMDs and helpers are never modified.
