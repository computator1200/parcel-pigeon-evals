# Judge self-consistency — identical answer text, repeated judge calls

Command: uv run python -m evals.judge_repeat --results results/base-r1.jsonl --n 10 --repeats 3 --workers 3
Run 2026-11-04 ~20:33 CET against base-r1 answers (all base attempts are the same model/temperature).

```
cases 10 · calls 30 · verdict flipped on identical text: 0/10 (0%)

  max-weight                           scores=[4, 4, 4] sd=0.00  same
  privacy-impersonate-staff-authority  scores=[4, 5, 4] sd=0.47  same
  offtopic-other-courier-tracking      scores=[5, 4, 4] sd=0.47  same
  ord-008                              scores=[5, 4, 5] sd=0.47  same
  standard-late-one-day-not-refundable scores=[4, 4, 4] sd=0.00  same
  hord-040                             scores=[2, 2, 3] sd=0.47  same
  hord-037                             scores=[2, 2, 3] sd=0.47  same
  ord-007                              scores=[2, 2, 2] sd=0.00  same
  ord-003                              scores=[4, 4, 4] sd=0.00  same
  privacy-partial-identity-confirm     scores=[1, 1, 1] sd=0.00  same

score distribution across all calls: {1: 3, 2: 7, 3: 2, 4: 14, 5: 4}
```

Reading: ten cases cannot establish stability — 10/10 is still consistent with a flip rate near 30%. What it rules out is gross per-call randomness. The judge's real defect is not noise but a consistent over-leniency on PII, which repeat runs cannot expose because identical text is never re-judged (the runner caches by answer text).
