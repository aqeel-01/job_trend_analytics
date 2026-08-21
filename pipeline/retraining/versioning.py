"""V1 model version helpers."""

from __future__ import annotations

import re

from pipeline.trend.models import DEFAULT_MODEL_VERSION

_VERSION_RE = re.compile(r"^v?(\d+)\.(\d+)$", re.IGNORECASE)


def parse_version(version: str) -> tuple[int, int]:
    """Parse a V1-style version string like ``v1.0`` into ``(major, minor)``."""
    match = _VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"Unsupported model version format: {version!r}")
    return int(match.group(1)), int(match.group(2))


def format_version(major: int, minor: int) -> str:
    return f"v{major}.{minor}"


def bump_minor_version(version: str | None = None) -> str:
    """
    Bump the minor component of a V1 model version.

    Examples:
        None / empty → v1.0
        v1.0 → v1.1
        v1.1 → v1.2
    """
    if version is None or not str(version).strip():
        return DEFAULT_MODEL_VERSION
    major, minor = parse_version(version)
    return format_version(major, minor + 1)


def initial_version() -> str:
    return DEFAULT_MODEL_VERSION
