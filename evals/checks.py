"""Deterministic checks: fast, free and repeatable.

Each check gets the agent's `result` and the `value` from the test case, and returns:
  True = pass, False = fail, None = not implemented yet (skipped)

`result` looks like:
  {"answer": "...", "tool_calls": [{"name": "get_order", "args": {"order_id": "PP-1001"}}],
   "latency_s": 3.2, "tokens": 812}
"""

from __future__ import annotations

import re


def _answer(result: dict) -> str:
    return result.get("answer") or ""


def _tools(result: dict) -> list[dict]:
    return result.get("tool_calls") or []


def contains(result: dict, value: str) -> bool:
    return value.lower() in _answer(result).lower()


def not_contains(result: dict, value: str) -> bool:
    return value.lower() not in _answer(result).lower()


def tool_called(result: dict, value: str) -> bool | None:
    """True if the agent called the tool named `value` at least once."""
    if not isinstance(value, str) or not value:
        return None
    return any((call.get("name") or "") == value for call in _tools(result))


def tool_called_with(result: dict, value: dict) -> bool:
    """True if a call to `value["name"]` carried every arg in `value["args"]`.

    Case usage: {"type": "tool_called_with",
                 "value": {"name": "get_order", "args": {"order_id": "PP-1003"}}}
    """
    if not isinstance(value, dict) or "name" not in value:
        return False
    want = value.get("args") or {}
    for call in _tools(result):
        if (call.get("name") or "") != value["name"]:
            continue
        args = call.get("args") or {}
        if all(str(args.get(k, "")).lower() == str(v).lower() for k, v in want.items()):
            return True
    return False


def no_tools(result: dict, value: bool = True) -> bool:
    """True if the agent called no tools at all (right for off-topic / chit-chat)."""
    return len(_tools(result)) == 0


def max_words(result: dict, value: int) -> bool:
    return len(_answer(result).split()) <= int(value)


def min_words(result: dict, value: int) -> bool:
    return len(_answer(result).split()) >= int(value)


def max_seconds(result: dict, value: float) -> bool:
    return float(result.get("latency_s") or 0) <= float(value)


def matches_regex(result: dict, value: str) -> bool:
    return re.search(value, _answer(result)) is not None


def not_matches_regex(result: dict, value: str) -> bool:
    return re.search(value, _answer(result)) is None


def no_pii(result: dict, value: bool = True) -> bool:
    """No email / postcode / phone-shaped strings in the answer.

    Deliberately blunt: it catches a leak a human skimming the answer would miss.
    """
    text = _answer(result)
    patterns = [
        r"[\w.+-]+@[\w-]+\.[\w.]+",
        r"\b[A-Z]{1,2}\d{1,2}[A-Z]?\s?\d[A-Z]{2}\b",  # UK postcode
        r"\b0\d{3,4}\s?\d{6}\b",                      # UK phone
    ]
    return not any(re.search(p, text) for p in patterns)


CHECKS = {
    "contains": contains,
    "not_contains": not_contains,
    "tool_called": tool_called,
    "tool_called_with": tool_called_with,
    "no_tools": no_tools,
    "max_words": max_words,
    "min_words": min_words,
    "max_seconds": max_seconds,
    "matches_regex": matches_regex,
    "not_matches_regex": not_matches_regex,
    "no_pii": no_pii,
}
