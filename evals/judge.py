"""LLM-as-judge: a second model grades each answer against rubric.md."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent.llm import client_for

RUBRIC = (Path(__file__).parent / "rubric.md").read_text()

# A 4/5 is "correct with a minor omission" — good enough to ship. 3 and below is not.
PASS_AT = 4


def _parse(raw: str) -> dict:
    """Models sometimes wrap JSON in prose or fences; dig the object out."""
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            raise ValueError(f"judge returned no JSON: {raw[:200]!r}")
        return json.loads(m.group(0))


def build_prompt(case: dict, result: dict) -> str:
    tools = ", ".join(t.get("name", "?") for t in result.get("tool_calls") or []) or "none"
    return (
        f"{RUBRIC}\n\n"
        f"---\n\n"
        f"CUSTOMER MESSAGE:\n{case['input']!r}\n\n"
        f"EXPECTED BEHAVIOUR:\n{case['expected']}\n\n"
        f"TOOLS THE ASSISTANT CALLED: {tools}\n\n"
        f"ASSISTANT'S ANSWER:\n{result.get('answer') or '(empty)'}\n"
    )


def judge(case: dict, result: dict) -> dict | None:
    """Return {"score": 1-5, "passed": bool, "reason": "..."}, or None to skip."""
    if not case.get("expected"):
        return None

    client, model = client_for("JUDGE")

    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": RUBRIC},
                {"role": "user", "content": build_prompt(case, result)},
            ],
        )
        data = _parse(resp.choices[0].message.content or "")
    except Exception as e:  # noqa: BLE001 — a broken judge must be loud, not a silent pass
        return {"score": 0, "passed": False, "reason": f"judge failed: {e}"}

    try:
        score = int(data.get("score", 0))
    except (TypeError, ValueError):
        score = 0
    score = max(0, min(5, score))
    reason = str(data.get("reason") or "").strip() or "no reason given"

    return {"score": score, "passed": score >= PASS_AT, "reason": reason}
