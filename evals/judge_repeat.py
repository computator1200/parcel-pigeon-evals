"""Does the judge agree with itself?

The runner caches a verdict per unique answer text, so a verdict flip in the
repeat runs only ever meant the answer text changed — it says nothing about the
judge's own stability. This module asks the direct question instead: give the
judge the SAME answer N times and see whether the verdict moves.

    uv run python -m evals.judge_repeat --results results/base-r1.jsonl --n 10 --repeats 3

Reports per-case score spread, the share of cases whose verdict flipped on
identical text, and the overall flip rate. A judge that flips here cannot be
used as a gate, whatever its agreement with a human looks like.
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals.judge import judge


def load(path: str) -> list[dict]:
    rows = []
    for line in Path(path).read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def spread(rows: list[dict], n: int, seed: int = 11) -> list[dict]:
    """Take a mix of judge passes and fails, so the sample isn't all one verdict."""
    scored = [r for r in rows if r.get("judge") and ((r.get("result") or {}).get("answer") or "").strip()]
    passed = [r for r in scored if r["judge"]["passed"]]
    failed = [r for r in scored if not r["judge"]["passed"]]
    half = n // 2
    import random

    random.seed(seed)
    picked = random.sample(passed, min(half, len(passed))) + random.sample(
        failed, min(n - half, len(failed))
    )
    return picked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    cases = spread(load(args.results), args.n)
    if not cases:
        print("no judgeable answers in that file")
        return 1

    jobs = [(c, k) for c in cases for k in range(args.repeats)]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        verdicts = list(pool.map(lambda j: (j[0]["case"]["id"], judge(j[0]["case"], j[0]["result"])), jobs))

    by_case: dict[str, list[dict]] = {}
    for case_id, verdict in verdicts:
        by_case.setdefault(case_id, []).append(verdict)

    flips = 0
    rows = []
    for case_id, vs in by_case.items():
        scores = [v["score"] for v in vs]
        passes = [v["passed"] for v in vs]
        flipped = len(set(passes)) > 1
        flips += flipped
        rows.append((case_id, scores, statistics.pstdev(scores), flipped))

    print(f"# Judge self-consistency: identical text, {args.repeats} calls each\n")
    print(f"cases {len(rows)} · calls {len(verdicts)} · verdict flipped on identical text: "
          f"{flips}/{len(rows)} ({100 * flips / len(rows):.0f}%)\n")
    for case_id, scores, sd, flipped in sorted(rows, key=lambda r: -int(r[3])):
        mark = "FLIP" if flipped else "same"
        print(f"  {case_id:<34} scores={scores} sd={sd:.2f}  {mark}")

    dist = Counter(s for _, sc, _, _ in rows for s in sc)
    print("\nscore distribution across all calls:", dict(sorted(dist.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
