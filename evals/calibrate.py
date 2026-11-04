"""Calibrate the judge against your own judgement.

  uv run python -m evals.calibrate sheet --results results/<run>.jsonl --n 8
  # read calibration.md, then set "human_pass": true/false in calibration.json
  uv run python -m evals.calibrate score

An uncalibrated judge is a random number generator with good manners. This gives
you the number to quote when they ask "do you trust your judge?" — plus the two
failure modes that decide whether you should:

  * DANGEROUS   judge passed, you failed it   -> ships a bad answer
  * CONSERVATIVE judge failed, you passed it  -> noise that hides real fixes

It also measures verbosity bias: judges reliably over-reward long answers.
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
JSON_OUT = ROOT / "calibration.json"
MD_OUT = ROOT / "calibration.md"


def load_results(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def pick(rows: list[dict], n: int, seed: int = 7) -> list[dict]:
    """Stratify: judge-pass and judge-fail, and anything the checks disagree with."""
    both = [r for r in rows if r.get("judge")]
    if not both:
        return []

    interesting = [r for r in both if r["judge"]["passed"] != bool(r.get("passed"))]
    passed = [r for r in both if r["judge"]["passed"]]
    failed = [r for r in both if not r["judge"]["passed"]]

    random.seed(seed)
    for group in (interesting, failed, passed):
        random.shuffle(group)

    # Half the sheet from disagreements (where the judge and the checks differ),
    # the rest split between passes and fails so agreement isn't measured on
    # failures alone — a judge that fails everything would otherwise look perfect.
    chosen: list[dict] = interesting[: max(2, n // 2)]
    pool: list[dict] = []
    for i in range(max(len(passed), len(failed))):
        if i < len(passed):
            pool.append(passed[i])
        if i < len(failed):
            pool.append(failed[i])
    for row in pool:
        if len(chosen) >= n:
            break
        if row not in chosen:
            chosen.append(row)
    for row in interesting + failed + passed:
        if len(chosen) >= n:
            break
        if row not in chosen:
            chosen.append(row)
    return chosen[:n]


def write_sheet(rows: list[dict], n: int) -> int:
    chosen = pick(rows, n)
    if not chosen:
        print("no judged rows in that results file — run without --no-judge first")
        return 2

    payload = []
    md = [
        "# Judge calibration",
        "",
        "Read each one and decide: **would you be happy for this answer to go to a customer?**",
        "Write `true` or `false` in `human_pass` for each entry in `calibration.json`,",
        "then run `uv run python -m evals.calibrate score`.",
        "",
        "Judging blind is the point — the judge's verdict is shown, but mark your own call first.",
        "",
    ]
    for i, row in enumerate(chosen, 1):
        case = row["case"]
        res = row["result"]
        j = row["judge"]
        payload.append(
            {
                "id": case["id"],
                "tags": case.get("tags", []),
                "input": case.get("input", ""),
                "expected": case.get("expected", ""),
                "answer": res.get("answer", ""),
                "tools": [t.get("name") for t in res.get("tool_calls") or []],
                "judge_score": j.get("score"),
                "judge_passed": j.get("passed"),
                "judge_reason": j.get("reason", ""),
                "human_pass": None,
            }
        )
        md += [
            f"### {i}. `{case['id']}`  —  judge {j.get('score')}/5 ({'PASS' if j.get('passed') else 'FAIL'})",
            "",
            f"**Customer:** {case.get('input')!r}",
            "",
            f"**Expected:** {case.get('expected')}",
            "",
            f"**Agent answered:** {res.get('answer') or '(empty)'}",
            "",
            f"**Tools:** {', '.join(t.get('name','?') for t in res.get('tool_calls') or []) or 'none'}",
            "",
            f"**Judge said:** {j.get('reason') or '(no reason)'}",
            "",
            "**Your verdict:** ___  (pass / fail)",
            "",
            "---",
            "",
        ]

    JSON_OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    MD_OUT.write_text("\n".join(md), encoding="utf-8")
    print(f"wrote {MD_OUT.relative_to(ROOT)} and {JSON_OUT.relative_to(ROOT)} ({len(payload)} answers)")
    print("next: fill in human_pass, then `uv run python -m evals.calibrate score`")
    return 0


def score() -> int:
    if not JSON_OUT.exists():
        print("no calibration.json — run `calibrate sheet` first")
        return 2
    data = json.loads(JSON_OUT.read_text(encoding="utf-8"))
    labelled = [d for d in data if d.get("human_pass") is not None]
    if len(labelled) < 3:
        print(f"only {len(labelled)} labelled — label at least 3 (8 is enough to be honest)")
        return 2

    agree = [d for d in labelled if bool(d["human_pass"]) == bool(d["judge_passed"])]
    dangerous = [d for d in labelled if d["judge_passed"] and not d["human_pass"]]
    conservative = [d for d in labelled if not d["judge_passed"] and d["human_pass"]]

    def mean_words(rows: list[dict]) -> float:
        return statistics.mean(len((r.get("answer") or "").split()) for r in rows) if rows else 0.0

    jp = [d for d in labelled if d["judge_passed"]]
    jf = [d for d in labelled if not d["judge_passed"]]
    w_pass, w_fail = mean_words(jp), mean_words(jf)

    print()
    print(f"agreement: {len(agree)}/{len(labelled)}  ({100 * len(agree) / len(labelled):.0f}%)")
    print(f"  DANGEROUS    {len(dangerous)}  (judge passed, you failed)")
    print(f"  CONSERVATIVE {len(conservative)}  (judge failed, you passed)")
    if w_pass and w_fail:
        ratio = w_pass / w_fail
        flag = "  <-- verbosity bias" if ratio >= 1.5 else ""
        print(f"  length: judge-pass {w_pass:.0f} words vs judge-fail {w_fail:.0f} ({ratio:.2f}x){flag}")

    if dangerous or conservative:
        print("\ndisagreements:")
        for d in dangerous + conservative:
            who = "judge passed / you failed" if d in dangerous else "judge failed / you passed"
            print(f"  - {d['id']} ({who}) score {d['judge_score']}: {d['judge_reason'][:100]}")
            print(f"      answer: {(d.get('answer') or '')[:140]}")

    tags: dict[str, list[bool]] = {}
    for d in labelled:
        for t in d.get("tags") or []:
            tags.setdefault(t, []).append(bool(d["human_pass"]) == bool(d["judge_passed"]))
    if tags:
        print("\nby tag: " + ", ".join(f"{t} {sum(v)}/{len(v)}" for t, v in sorted(tags.items())))

    print(
        "\nquote it as: \"the judge agreed with my hand labels on "
        f"{len(agree)}/{len(labelled)}\""
        + (f", and it over-rewards length ({ratio:.1f}x)" if w_pass and w_fail and w_pass / w_fail >= 1.5 else "")
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sheet")
    s.add_argument("--results", required=True, type=Path)
    s.add_argument("--n", type=int, default=8)
    sub.add_parser("score")
    args = ap.parse_args()

    if args.cmd == "sheet":
        return write_sheet(load_results(args.results), args.n)
    return score()


if __name__ == "__main__":
    sys.exit(main())
