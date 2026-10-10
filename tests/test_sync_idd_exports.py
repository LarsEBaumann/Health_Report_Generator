"""The IDD server streams without Content-Length, so downloads must be confirmed."""
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import sync_idd_exports as sync  # noqa: E402

GOOD = b"a,b\n1,2\n3,4\n"
OTHER = b"a,b\n1,2\n5,6\n"
THIRD = b"a,b\n1,2\n7,8\n"
CUT = b"a,b\n1,2\n3"


class Response:
    def __init__(self, content):
        self.content = content

    def raise_for_status(self):
        pass


class Session:
    def __init__(self, *items):
        self.items = list(items)
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        item = self.items.pop(0)
        if isinstance(item, Exception):
            raise item
        return Response(item)


def test_cut_off_csv_is_rejected_by_validation():
    with pytest.raises(ValueError):
        sync.csv_info(CUT)


def test_two_identical_downloads_are_accepted_after_a_cut_off_one():
    session = Session(CUT, GOOD, GOOD)
    content, columns, rows = sync.fetch_validated_csv(session, "u")
    assert (content, columns, rows) == (GOOD, ["a", "b"], 2)
    assert session.calls == 3


def test_match_with_committed_hash_is_accepted_at_once():
    session = Session(GOOD)
    content, _, _ = sync.fetch_validated_csv(session, "u", known_sha=sync.sha256_bytes(GOOD))
    assert content == GOOD
    assert session.calls == 1


def test_three_different_downloads_fail():
    with pytest.raises(RuntimeError):
        sync.fetch_validated_csv(Session(GOOD, OTHER, THIRD), "u")


def test_a_cut_download_between_two_good_ones_does_not_confirm():
    with pytest.raises(RuntimeError):
        sync.fetch_validated_csv(Session(GOOD, CUT, GOOD), "u")


def test_network_errors_are_retried():
    session = Session(requests.ConnectionError("reset"), GOOD, GOOD)
    content, _, _ = sync.fetch_validated_csv(session, "u")
    assert content == GOOD
