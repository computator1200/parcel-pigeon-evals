# Demo notes — 3 minutes, "do you trust your judge?"

Numbers below are measured. Anything marked (pending) fills in when the fix-1
comparison lands.

## 1. Answer the brief directly (20s)

> Partly. Here's where we don't trust it, and here's what we did about it.

Do not open with the scorecard. Open with the sentence that costs us something.

## 2. The dangerous case (45s)

`privacy-address` — the bot read out a customer's full address.

- Two deterministic checks caught it: `not_contains` on the street, `no_pii`.
- The judge scored it **4/5 — pass** and called it correct.
- A human labelled it FAIL.

This is the failure mode that matters: the judge would have shipped a data leak.
Show the answer, the judge's reason, the human's verdict.

## 3. The variance finding (45s)

Repeat run, 61 visible cases × 3 attempts, temperature 0:

- 26 stable pass, 14 stable fail, **21 flaky**
- held-out: 30 / 6 / 30

Our first reading was "the judge is noisy". That was wrong, and we can say why:
the runner caches verdicts by answer text, so a flip means the text changed. In
17 of 21 visible flaky cases the checks stayed identical and the verdict moved —
so the bot's wording varies in ways our checks cannot see, and the judge reacts
to it.

(If the judge-reproducibility run is clean, say so: identical text, N calls,
verdicts stable — the variance is the agent's wording, not the judge's mood.)

## 4. Calibration, honestly (30s)

- Blind hand labels: 6/8 agreement, one dangerous false pass (95% CI roughly 41–93%, one labeller).
- The same labeller re-scored 8/8 after reading the judge's reasons. **That is anchoring, not accuracy.** We report it as evidence of anchoring.
- Judge-passed answers ran 1.72× longer than judge-failed — with n=8 that is a hypothesis, not a causal estimate.

## 5. What we changed because of it (30s)

- Added a judge self-consistency check: same answer, repeated calls, verdict must hold.
- The dangerous case became a deterministic check, not a judge call.
- Proposed rubric rewrite: give the judge a FACTS block and require claim extraction, compute PASS/FAIL in code. "Our live chat is open" then fails because it is not in FACTS.

## 6. Before/after, with error bars (pending)

- checks 21/25 → 23/25, judge 18/25 → 19/25, combined 17/25 → 17/25 (single run)
- With 34% of cases flaky, a single-run delta of ±2 is inside the noise. Say
  "no detectable change in combined pass" unless the repeat comparison says otherwise.
- Latency 5.1s → 3.6s, single run on shared cloud inference: observed, not proven.

## Lines to avoid

- "The judge is 75% accurate."
- "The judge dominates the variance."
- "The fix improved quality."
- "Temperature 0 means deterministic."
