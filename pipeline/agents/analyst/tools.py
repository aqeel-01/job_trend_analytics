"""Analyst Agent tools — fetch and interpret ML model output from the FastAPI layer."""

import logging

import httpx

logger = logging.getLogger(__name__)


def fetch_trending_skills(
    base_url: str = "http://127.0.0.1:8000",
    limit: int = 200,
    timeout: float = 10.0,
) -> dict:
    """Call GET /trending-skills and return the parsed JSON response.

    Returns a dict with keys:
        success (bool), data (dict|None), detail (str).
    """
    try:
        resp = httpx.get(
            f"{base_url}/trending-skills",
            params={"limit": limit},
            timeout=timeout,
        )
        if resp.status_code != 200:
            return {
                "success": False,
                "data": None,
                "detail": f"HTTP {resp.status_code}: {resp.text[:200]}",
            }
        body = resp.json()
        return {"success": True, "data": body, "detail": "ok"}
    except httpx.ConnectError:
        return {"success": False, "data": None, "detail": "connection refused — API not running"}
    except Exception as exc:
        logger.exception("fetch_trending_skills failed")
        return {"success": False, "data": None, "detail": f"error: {exc}"}


def fetch_model_info(
    base_url: str = "http://127.0.0.1:8000",
    timeout: float = 5.0,
) -> dict:
    """Call GET /model-info and return the parsed JSON response."""
    try:
        resp = httpx.get(f"{base_url}/model-info", timeout=timeout)
        if resp.status_code != 200:
            return {"success": False, "data": None, "detail": f"HTTP {resp.status_code}"}
        return {"success": True, "data": resp.json(), "detail": "ok"}
    except Exception as exc:
        logger.exception("fetch_model_info failed")
        return {"success": False, "data": None, "detail": f"error: {exc}"}


# ---------------------------------------------------------------------------
# Interpretation helpers — pure functions, no side effects
# ---------------------------------------------------------------------------

STRONG_CHANGE_PERCENT_THRESHOLD = 100.0
WEAK_CHANGE_PERCENT_THRESHOLD = 20.0


def classify_signal_strength(
    z_score: float | None,
    change_percent: float | None,
    trend: str,
) -> str:
    """Return 'strong' or 'weak' based on z-score and change_percent."""
    if trend == "insufficient_data":
        if change_percent is not None and abs(change_percent) >= STRONG_CHANGE_PERCENT_THRESHOLD:
            return "strong"
        return "weak"
    if z_score is not None and abs(z_score) >= 1.0:
        return "strong"
    if change_percent is not None and abs(change_percent) >= STRONG_CHANGE_PERCENT_THRESHOLD:
        return "strong"
    return "weak"


def interpret_direction(raw_direction: str) -> str:
    """Map the API direction value to our MovementDirection enum value."""
    mapping = {"up": "rising", "down": "falling", "flat": "stable"}
    return mapping.get(raw_direction, "unknown")
