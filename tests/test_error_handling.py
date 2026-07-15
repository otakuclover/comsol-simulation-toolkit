"""Tests for error propagation in low-level COMSOL helpers.

These use lightweight fake collection objects and do not require COMSOL.
"""

import logging

import pytest

from comsol_toolkit.comsol_helpers import remove_if_exists, tags


class FakeCollection:
    """Minimal stand-in for a COMSOL collection (study/dataset/feature)."""

    def __init__(self, tag_list, *, tags_raise=False, remove_raise=False):
        self._tags = list(tag_list)
        self._tags_raise = tags_raise
        self._remove_raise = remove_raise
        self.removed = []

    def tags(self):
        if self._tags_raise:
            raise RuntimeError("boom while listing tags")
        return list(self._tags)

    def remove(self, tag):
        if self._remove_raise:
            raise RuntimeError("boom while removing")
        self.removed.append(tag)
        self._tags.remove(tag)


def test_tags_returns_string_list():
    assert tags(FakeCollection(["eig1", "dset1"])) == ["eig1", "dset1"]


def test_tags_propagates_errors():
    """tags() must NOT swallow a broken handle into an empty list."""
    with pytest.raises(RuntimeError, match="boom while listing tags"):
        tags(FakeCollection([], tags_raise=True))


def test_remove_if_exists_removes_present_tag():
    coll = FakeCollection(["eig1", "eig2"])
    remove_if_exists(coll, "eig1")
    assert coll.removed == ["eig1"]
    assert "eig1" not in coll.tags()


def test_remove_if_exists_noop_for_absent_tag():
    coll = FakeCollection(["eig1"])
    remove_if_exists(coll, "missing")
    assert coll.removed == []


def test_remove_if_exists_logs_when_listing_fails(caplog):
    coll = FakeCollection([], tags_raise=True)
    with caplog.at_level(logging.WARNING):
        remove_if_exists(coll, "eig1")
    assert any("Could not list tags" in r.message for r in caplog.records)


def test_remove_if_exists_logs_when_removal_fails(caplog):
    coll = FakeCollection(["eig1"], remove_raise=True)
    with caplog.at_level(logging.WARNING):
        remove_if_exists(coll, "eig1")
    assert any("Failed to remove existing tag" in r.message for r in caplog.records)
