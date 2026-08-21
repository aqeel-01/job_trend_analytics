"""Tests for V1 model versioning helpers."""

import pytest

from pipeline.retraining.versioning import (
    bump_minor_version,
    format_version,
    initial_version,
    parse_version,
)


def test_initial_version() -> None:
    assert initial_version() == "v1.0"


def test_bump_from_none() -> None:
    assert bump_minor_version(None) == "v1.0"
    assert bump_minor_version("") == "v1.0"


def test_bump_minor() -> None:
    assert bump_minor_version("v1.0") == "v1.1"
    assert bump_minor_version("v1.1") == "v1.2"
    assert bump_minor_version("1.9") == "v1.10"


def test_parse_and_format() -> None:
    assert parse_version("v1.0") == (1, 0)
    assert format_version(1, 1) == "v1.1"


def test_invalid_version() -> None:
    with pytest.raises(ValueError):
        parse_version("2.0.1")
