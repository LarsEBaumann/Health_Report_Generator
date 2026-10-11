"""Translate the minimal web request into validated pipeline settings."""

import json
import tempfile
from pathlib import Path

from analyse import load_config

PRESETS = Path(__file__).resolve().parent / "config" / "stakeholders"
AUDIENCES = ("public", "health_institution", "researcher")
SUPPORTED_WINDOWS = ((2021, 2025), (2022, 2025))


def build_stakeholder(payload):
    """Return server-controlled settings; never execute or render a request."""
    if type(payload) is not dict:
        raise ValueError("Request must be a JSON object.")

    if set(payload) - {"audience", "years"}:
        raise ValueError("Unsupported request fields.")

    audience = payload.get("audience")
    if type(audience) is not str or audience not in AUDIENCES:
        raise ValueError("Choose a supported audience.")

    cfg = load_config(PRESETS / f"{audience}.json")
    years = payload.get("years", cfg["years"])

    if (
        type(years) is not list
        or len(years) != 2
        or any(type(year) is not int for year in years)
    ):
        raise ValueError("Years must be a list of two integers.")

    if tuple(years) not in SUPPORTED_WINDOWS:
        raise ValueError("Choose a supported reporting window.")

    cfg["years"] = list(years)
    start, end = years
    reference = cfg["reference_year"]
    period = f"{start}-{end}"

    if audience == "public":
        cfg["title"] = (
            f"Infectious disease notifications in Switzerland and "
            f"Liechtenstein: {period}"
        )
        cfg["question"] = (
            f"How did reported cases change during {period} and relative "
            f"to {reference}, and how sure can we be?"
        )
    elif audience == "health_institution":
        cfg["title"] = f"Notifiable disease monitoring brief: {period}"
        cfg["question"] = (
            f"Which notifiable viral and bacterial diseases reported in "
            f"Switzerland and Liechtenstein changed most in {end} compared "
            f"with {reference}, how did they develop during {period}, and "
            f"what limitations should monitoring staff consider?"
        )
    else:
        cfg["title"] = f"Viral and bacterial notifications: {period}"
        cfg["question"] = (
            f"How did viral and bacterial notifiable infectious diseases "
            f"in Switzerland and Liechtenstein develop during {period} "
            f"relative to {reference}, and how robust is the comparison "
            f"to selection rules and the influenza sensitivity exclusion?"
        )

    with tempfile.TemporaryDirectory(prefix="sourceprism-request-") as tmp:
        path = Path(tmp) / "stakeholder.json"
        path.write_text(json.dumps(cfg), encoding="utf-8")
        return load_config(path)
