"""Smoke test: package imports cleanly. Replace/extend as modules land."""

import curlbook


def test_version_is_set() -> None:
    assert curlbook.__version__
