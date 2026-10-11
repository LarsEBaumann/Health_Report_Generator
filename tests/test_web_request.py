import json

import pytest

from web_request import (
    AUDIENCES,
    PRESETS,
    SUPPORTED_WINDOWS,
    build_stakeholder,
)


@pytest.mark.parametrize("audience", AUDIENCES)
@pytest.mark.parametrize("years", SUPPORTED_WINDOWS)
def test_supported_requests_preserve_science(audience, years):
    preset = json.loads((PRESETS / f"{audience}.json").read_text())
    payload = {"audience": audience, "years": list(years)}
    result = build_stakeholder(payload)

    assert result["years"] == list(years)
    assert f"{years[0]}-{years[1]}" in result["title"]
    assert f"{years[0]}-{years[1]}" in result["question"]

    for key, value in preset.items():
        if key not in {"years", "title", "question"}:
            assert result[key] == value

    assert payload == {"audience": audience, "years": list(years)}


@pytest.mark.parametrize("audience", AUDIENCES)
def test_default_window(audience):
    assert build_stakeholder({"audience": audience})["years"] == [2021, 2025]


@pytest.mark.parametrize("payload", [
    None,
    [],
    {},
    {"audience": None},
    {"audience": []},
    {"audience": "../public"},
    {"audience": "unknown"},
    {"audience": "public", "years": None},
    {"audience": "public", "years": "2021-2025"},
    {"audience": "public", "years": [2021]},
    {"audience": "public", "years": [True, 2025]},
    {"audience": "public", "years": [2021.0, 2025]},
    {"audience": "public", "years": [2025, 2021]},
    {"audience": "public", "years": [1900, 2200]},
    {"audience": "public", "geography": "CH"},
    {"audience": "public", "title": "<script>alert(1)</script>"},
    {"audience": "public", "out": "/tmp/report"},
    {"audience": "public", "source_priority": []},
])
def test_invalid_requests_are_rejected(payload):
    with pytest.raises(ValueError):
        build_stakeholder(payload)


def test_returned_settings_are_independent():
    first = build_stakeholder({"audience": "public"})
    first["years"][0] = 1900
    first["source_priority"].clear()

    second = build_stakeholder({"audience": "public"})
    assert second["years"] == [2021, 2025]
    assert second["source_priority"]
