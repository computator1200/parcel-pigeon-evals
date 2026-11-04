"""Parcel Pigeon's support agent: the system you are evaluating.

Try it:  uv run python -m agent.agent "How much is Next Day delivery?"
"""

import json
import sys
import time
from pathlib import Path

from agent.llm import client_for
from agent.tools import TOOL_SCHEMAS, TOOLS

SYSTEM_PROMPT_FILE = Path(__file__).parent / "system_prompt.md"


def run_agent(question: str, max_steps: int = 8) -> dict:
    """Answer one customer question. Returns the answer plus what happened along the way."""
    client, model = client_for("AGENT")
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_FILE.read_text()},
        {"role": "user", "content": question},
    ]
    tool_calls, tokens = [], 0
    answer = "(agent gave up: too many steps)"
    start = time.perf_counter()
    cache: dict[str, str] = {}      # identical calls return the same answer, not a new round trip
    nudged = False

    for _ in range(max_steps):
        kwargs = {"model": model, "messages": messages, "temperature": 0}
        if not nudged:
            kwargs["tools"] = TOOL_SCHEMAS
        response = client.chat.completions.create(**kwargs)
        tokens += response.usage.total_tokens if response.usage else 0
        message = response.choices[0].message

        if not message.tool_calls:
            answer = message.content or ""
            break

        messages.append(message.model_dump(exclude_none=True))
        fresh = 0
        for call in message.tool_calls:
            try:
                args = json.loads(call.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            key = f"{call.function.name}:{json.dumps(args, sort_keys=True)}"
            if key in cache:
                output = cache[key]
            else:
                try:
                    output = TOOLS[call.function.name](**args)
                except Exception as e:  # noqa: BLE001 — a bad tool call must not kill the turn
                    output = f"Tool error: {e}"
                cache[key] = output
                fresh += 1
            tool_calls.append({"name": call.function.name, "args": args})
            messages.append({"role": "tool", "tool_call_id": call.id, "content": output})

        if fresh == 0 and not nudged:
            # every call this turn was a repeat: stop digging and make it answer
            messages.append({
                "role": "system",
                "content": "You already have every fact you need from the tool results above. "
                           "Do not call any more tools. Answer the customer's question now, briefly.",
            })
            nudged = True

    return {
        "answer": answer,
        "tool_calls": tool_calls,
        "latency_s": round(time.perf_counter() - start, 2),
        "tokens": tokens,
    }


if __name__ == "__main__":
    result = run_agent(" ".join(sys.argv[1:]) or "How much is Next Day delivery?")
    print(json.dumps(result, indent=2, ensure_ascii=False))
