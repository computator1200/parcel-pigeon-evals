"""Merge the team's case files into one suite, with validation.

  uv run python -m evals.merge_cases
  uv run python -m evals.merge_cases --out evals/cases.all.jsonl
  uv run python -m evals.run --cases evals/cases.all.jsonl --label baseline

Why this exists: six people writing cases in six files is fast, but the runner
takes one file. This is the seam. It fails loudly on the mistakes that would
otherwise show up as silent ➖ rows in the scorecard:
  * invalid JSON (reported with file:line)
  * a case with no id / input / expected
  * the same id in two files
  * an unknown check type (the checker would return None = not scored)
  * a case with nothing to score it (no checks AND no expected)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
DEFAULT_GLOB = "cases*.jsonl"
OUT = ROOT / "evals" / "cases.all.jsonl"

try:
    from evals.checks import CHECKS as KNOWN_CHECKS
except Exception:  # noqa: BLE001 — allow running the merger standalone
    KNOWN_CHECKS = {}


def load_file(path: Path, errors: list[str], warnings: list[str]) -> list[dict]:
    cases: list[dict] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as e:
            errors.append(f"{path.name}:{lineno} invalid JSON — {e.msg}")
            continue

        cid = case.get("id")
        if not cid:
            errors.append(f"{path.name}:{lineno} missing 'id'")
            continue
        if not case.get("input") and case.get("input") != "":
            errors.append(f"{path.name}:{lineno} ({cid}) missing 'input'")
        if not case.get("expected"):
            warnings.append(f"{path.name}:{lineno} ({cid}) has no 'expected' — the judge will skip it")
        if not case.get("checks") and not case.get("expected"):
            errors.append(f"{path.name}:{lineno} ({cid}) has neither checks nor expected — nothing can score it")

        for chk in case.get("checks") or []:
            ctype = chk.get("type")
            if KNOWN_CHECKS and ctype not in KNOWN_CHECKS:
                errors.append(f"{path.name}:{lineno} ({cid}) unknown check type '{ctype}'")

        cases.append(case)
    return cases


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT), type=Path)
    ap.add_argument("--glob", default=DEFAULT_GLOB, help="filename pattern inside evals/")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = ap.parse_args()

    files = sorted((ROOT / "evals").glob(args.glob))
    # never merge the merge output back in (it matches cases*.jsonl on a second run)
    out_resolved = args.out.resolve()
    files = [f for f in files if f.resolve() != out_resolved and f.name != "cases.all.jsonl"]
    if not files:
        print(f"no case files matched evals/{args.glob}")
        return 2

    errors: list[str] = []
    warnings: list[str] = []
    merged: list[dict] = []
    seen: dict[str, str] = {}

    for path in files:
        cases = load_file(path, errors, warnings)
        print(f"{path.name:<28} {len(cases):>3} case(s)")
        for c in cases:
            cid = c["id"]
            if cid in seen:
                errors.append(f"duplicate id '{cid}' in {path.name} (first seen in {seen[cid]})")
                continue
            seen[cid] = path.name
            merged.append(c)

    # near-duplicates: same question asked twice under different ids
    by_input = Counter((c.get("input") or "").strip().lower() for c in merged)
    for text, n in by_input.items():
        if n > 1 and text:
            ids = [c["id"] for c in merged if (c.get("input") or "").strip().lower() == text]
            warnings.append(f"identical input in {n} cases: {', '.join(ids)}")

    scored = [c for c in merged if c.get("checks") or c.get("expected")]
    judged = [c for c in merged if c.get("expected")]
    tagged = Counter(t for c in merged for t in (c.get("tags") or []))

    print()
    if warnings:
        print(f"{len(warnings)} warning(s):")
        for w in warnings[:20]:
            print(f"  ! {w}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more")
        print()

    if errors:
        print(f"{len(errors)} ERROR(S) — nothing written:")
        for e in errors[:30]:
            print(f"  x {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")
        return 1

    if args.strict and warnings:
        print("--strict: refusing to write with warnings")
        return 1

    args.out.write_text(
        "\n".join(json.dumps(c, ensure_ascii=False) for c in merged) + "\n", encoding="utf-8"
    )
    print(f"merged {len(merged)} cases -> {args.out.relative_to(ROOT)}")
    print(f"  scoreable: {len(scored)}   judge-scored: {len(judged)}/{len(merged)}")
    print("  tags: " + ", ".join(f"{t} {n}" for t, n in tagged.most_common()))
    print(f"\nnow run:  uv run python -m evals.run --cases {args.out.relative_to(ROOT)} --label merged")
    return 0


if __name__ == "__main__":
    sys.exit(main())
