"""
Tools the agent can call. Two properties matter more than what they compute:

  - every tool can fail, and callers must deal with it (`call_tool` retries with
    backoff and gives up cleanly with a ToolError);
  - arithmetic that decides money (refund window) is plain code, never the model.

`get_patch_status` stands in for the live deployment API. It is deterministic by
default; set TOOL_FAILURE_RATE=0.5 to make it flaky and watch the retry path.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass
from datetime import date, timedelta

STANDARD_REFUND_WINDOW_DAYS = 14

# What the live "deployment status" service knows. 3.5.0 is deliberately absent
# from the corpus: only a tool call can answer whether it is live.
_LIVE_PATCHES = {
    "3.1.0": "live", "3.2.0": "live", "3.3.0": "live", "3.3.1": "superseded",
    "3.3.2": "live", "3.4.0": "live", "3.5.0": "staged, not live",
}

_rng = random.Random(int(os.getenv("TOOL_SEED", "7")))


class ToolError(RuntimeError):
    pass


@dataclass
class ToolResult:
    name: str
    ok: bool
    value: object
    attempts: int


def get_patch_status(version: str) -> dict:
    """Simulated call to the deployment API. Raises on transient failure."""
    failure_rate = float(os.getenv("TOOL_FAILURE_RATE", "0"))
    if _rng.random() < failure_rate:
        raise ToolError("deployment API timed out")
    status = _LIVE_PATCHES.get(version)
    if status is None:
        return {"version": version, "status": "unknown", "live": False}
    return {"version": version, "status": status, "live": status == "live"}


def refund_days_left(days_since_purchase: int | None = None,
                     purchase_date: str | None = None,
                     today: str | None = None) -> dict:
    """Deterministic refund-window arithmetic. Never delegated to the model."""
    if days_since_purchase is None:
        if purchase_date is None:
            raise ToolError("need days_since_purchase or purchase_date")
        ref = date.fromisoformat(today) if today else date.today()
        days_since_purchase = (ref - date.fromisoformat(purchase_date)).days
    if days_since_purchase < 0:
        raise ToolError("purchase date is in the future")
    left = STANDARD_REFUND_WINDOW_DAYS - days_since_purchase
    return {
        "window_days": STANDARD_REFUND_WINDOW_DAYS,
        "days_since_purchase": days_since_purchase,
        "days_left": max(left, 0),
        "inside_window": left > 0,
    }


def days_between(start: str, end: str) -> dict:
    d = (date.fromisoformat(end) - date.fromisoformat(start)).days
    return {"start": start, "end": end, "days": d, "hours": d * 24}


def within_hours(event: str, moment: str, hours: int) -> dict:
    delta = date.fromisoformat(moment) - date.fromisoformat(event)
    return {"within": timedelta(0) <= delta <= timedelta(hours=hours), "hours": hours}


TOOLS = {
    "get_patch_status": {
        "fn": get_patch_status,
        "description": "Check whether a patch version is currently live in production.",
        "parameters": {"type": "object", "properties": {"version": {"type": "string"}},
                       "required": ["version"]},
    },
    "refund_days_left": {
        "fn": refund_days_left,
        "description": "Compute days left in the 14-day standard refund window.",
        "parameters": {"type": "object", "properties": {
            "days_since_purchase": {"type": "integer"},
            "purchase_date": {"type": "string", "description": "YYYY-MM-DD"}}},
    },
    "days_between": {
        "fn": days_between,
        "description": "Days and hours between two YYYY-MM-DD dates.",
        "parameters": {"type": "object", "properties": {
            "start": {"type": "string"}, "end": {"type": "string"}},
            "required": ["start", "end"]},
    },
}


def call_tool(name: str, args: dict, retries: int = 3, backoff: float = 0.05) -> ToolResult:
    """Run a tool with bounded retries. Never raises: failure is a result."""
    if name not in TOOLS:
        return ToolResult(name, False, f"unknown tool {name}", 0)
    fn = TOOLS[name]["fn"]
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            return ToolResult(name, True, fn(**args), attempt)
        except (ToolError, TypeError, ValueError) as exc:
            last_error = str(exc)
            if attempt < retries:
                time.sleep(backoff * attempt)
    return ToolResult(name, False, f"gave up after {retries} attempts: {last_error}", retries)


def openai_tool_specs() -> list[dict]:
    return [{"type": "function", "function": {
        "name": name, "description": spec["description"], "parameters": spec["parameters"]}}
        for name, spec in TOOLS.items()]
