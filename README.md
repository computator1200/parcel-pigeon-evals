# Judge the Agent — an eval harness for Parcel Pigeon's support bot

**Does the bot deserve to go live next week? This repo answers that with numbers.**

An evaluation harness built in one evening at [Judge the Agent](https://luma.com/h8zer2ek) (The Friendly Data Meetup London, Quantspark Blackfriars, 4 November 2026). It ships a deliberately weak customer-support agent, a growing suite of adversarial test cases, deterministic checks, an LLM judge — and the tooling to prove a fix actually worked rather than just feel like it did.

The question the hosts cared about most: **do you trust your judge?** So the repo measures that too.

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![uv](https://img.shields.io/badge/managed%20with-uv-261230)
![cases](https://img.shields.io/badge/cases-61%20visible%20%2B%2066%20held--out-informational)
![judge](https://img.shields.io/badge/judge-LLM%20%2B%20deterministic%20checks-6f42c1)
![license](https://img.shields.io/badge/license-MIT-green)

---

## What's measured

Three signals, deliberately kept separate, because they fail differently:

| Signal | What it tells you | Implemented in |
|---|---|---|
| **Deterministic checks** | Did the answer contain the right facts and avoid the wrong ones? | `evals/checks.py` — 11 check types |
| **LLM judge** | Would a reasonable person accept this answer? | `evals/judge.py` + `evals/rubric.md` |
| **Human calibration** | Is the judge right? | `evals/calibrate.py` |

A case can pass every check and fail the judge — that's the interesting data, not noise to average away. The harness reports those separately instead of collapsing them into one pass rate.

## Results from the run in this repo

61 visible cases + 66 held-out, **3 attempts each at temperature 0**, agent and judge both `minimax-m3.1-flash` (Ollama Cloud), 4 November 2026. A case counts as a stable pass only if every attempt passed.

| | Base | After the fix |
|---|---|---|
| Visible: stable pass / fail / flaky | 26 / 14 / 21 | **34 / 8 / 19** |
| Held-out: stable pass / fail / flaky | 30 / 6 / 30 | **49 / 1 / 16** |
| Visible stable fail → pass / pass → fail | — | **2 / 1** |
| Held-out stable fail → pass / pass → fail | — | **4 / 1** |
| Visible cases failing on the judge alone (every check passed) | 22 | 20 |

What that supports, and what it doesn't:

- **The fix is real, but modest — quote the transition, not the total.** Held-out: 4 cases went stable fail → stable pass, 1 went stable pass → stable fail. Visible: 2 and 1. The held-out total rose 30 → 49 mostly because 22 flaky cases happened to settle into passing, which is the same regression to the mean that inflates the visible number. The 4-vs-2 comparison is the defensible claim: the fix worked better on cases the fixer never saw.
- **Visible +8 stable passes is partly regression to the mean.** 19 cases are still flaky, so 26 → 34 includes movement that would have happened anyway.
- **Most remaining visible failures are judge-only** — 20 cases pass every deterministic check and fail the judge. Before blaming the bot, look at the judge.
- **A single run tells you almost nothing.** The 25-case single-run scorecard we ran first said "17/25 before, 17/25 after" with 4 fixed and 4 broken. Same code, same cases, different story: at 34% flakiness, a one-run delta of ±2 is inside the noise.

### Judge self-consistency

Same answer text, three judge calls each, ten cases: verdict identical in 10/10, score moved by one point in 4/10 (e.g. 4,5,4).

Read that narrowly: ten cases cannot establish stability — 10/10 is still consistent with a flip rate near 30%. What it does rule out is gross per-call randomness, and it points the finger at the agent rewriting its answers. The judge's real defect is not noise: it is a consistent over-leniency about PII, which repeat runs cannot reveal because identical text is never re-judged.

### Calibration

One teammate hand-labelled a random draw of 8 base-run answers blind: **7/8 agreement (95% CI 53–98%)**, one **DANGEROUS** disagreement (judge passed an answer containing a customer's name and address), zero conservative. He then re-scored 8/8 after reading the judge's reasons — that is anchoring, not accuracy, and is reported as such.


## Quick start

You need [uv](https://docs.astral.sh/uv/getting-started/installation/) and either Docker (for local models) or any OpenAI-compatible endpoint.

```bash
cp .env.example .env
docker compose up -d                                   # local LLMs
docker compose exec ollama ollama pull llama3.2:3b     # the agent
docker compose exec ollama ollama pull qwen2.5:7b      # the judge
uv run python -m agent.agent "How much is Next Day delivery?"
```

You should get back an answer mentioning **£6.50**. Then run the suite:

```bash
uv run python -m evals.run --label baseline
```

Using a hosted model instead? See [docs/providers.md](docs/providers.md).

## Commands

| Command | What it does |
|---|---|
| `uv run python -m agent.agent "…"` | Ask the bot one question |
| `uv run python -m evals.run --label <name>` | Run the suite, write `results/<ts>-<name>.jsonl` |
| `uv run python -m evals.compare a.jsonl b.jsonl` | Before/after table with 🟢 fixed / 🔴 broke |
| `uv run python -m evals.merge_cases` | Merge every `evals/cases*.jsonl`, validating as it goes |
| `uv run python -m evals.calibrate sheet --results r.jsonl --n 8` | Build a hand-labelling sheet |
| `uv run python -m evals.calibrate score` | Agreement %, DANGEROUS/CONSERVATIVE split, verbosity bias |
| `uv run python -m evals.intensive run --label base` | Repeats + held-out split + flaky/inconclusive accounting |
| `uv run python -m evals.intensive flaky base` | Splits flaky cases: bot changed vs checks couldn't see it |
| `uv run python -m evals.intensive compare base fix-1` | Stable fail→pass only, with flaky counted separately |
| `uv run python -m evals.judge_repeat --results results/base-r1.jsonl` | Same answer, repeated judge calls — is the judge stable? |

Useful flags: `--only <case-id>`, `--no-judge`, `--workers N`.

### Why the extra tools exist

- **`merge_cases`** — six people writing cases in six files is fast; the runner takes one. It fails loudly on invalid JSON (reported `file:line`), duplicate ids across files, unknown check types, and cases with nothing able to score them. An unknown check type silently scores as "not implemented" and looks like a gap in the demo, so this refuses to write.
- **`calibrate`** — an uncalibrated judge is a random number generator with good manners. Hand-label 8 answers and it reports agreement, splits disagreements into **DANGEROUS** (judge passed, you failed it — ships a bad answer) and **CONSERVATIVE** (judge failed, you passed it — noise that hides real fixes), and reports the length difference between passed and failed answers. Sample it **randomly** (`--random`): a stratified sheet picks the interesting cases by design and cannot support an accuracy claim. On the random draw in this repo: 7/8 agreement, 1 dangerous, 0 conservative.
- **`intensive`** — repeats every case 3× and counts a case once. Pass = all repeats pass, fail = none do, flaky = both; a fix only counts as stable-fail → stable-pass. Crashed agents and broken judges are **inconclusive**, which is never a pass. Held-out cases are shown as ids and totals only, so the person fixing the bot can run them without seeing them.

## Test case format

One JSON object per line, ids prefixed by area so merges can't collide (`ord-`, `pol-`, `saf-`):

```json
{"id":"ord-014","input":"My parcel is late — where is it?","expected":"Looks up the order, states status and expected date; does not promise a refund","checks":[{"type":"tool_called","value":"get_order"},{"type":"not_contains","value":"refund"}],"tags":["order","dates"]}
```

Every case needs an `expected` value, or the judge skips it and it shows as un-scored.

Available checks: `contains`, `not_contains`, `matches_regex`, `not_matches_regex`, `tool_called`, `tool_called_with`, `no_tools`, `max_words`, `min_words`, `max_seconds`, `no_pii`.

## Project map

```
agent/                  the bot under test
├── agent.py            loop: tools, cached identical calls, forced answer on repeat turns
├── system_prompt.md    its instructions
├── tools.py            get_order, search_policies
└── data/               policies + orders (the ground truth)

evals/
├── cases.jsonl         core suite
├── cases-orders.jsonl  order-flow cases
├── cases-policy.jsonl  price / weight / cut-off cases
├── cases-safety.jsonl  privacy, injection, adversarial
├── checks.py           11 deterministic checks
├── judge.py            LLM judge (rubric-graded, JSON output)
├── rubric.md           the marking scheme
├── run.py              runner → results/
├── compare.py          before vs after
├── merge_cases.py      validate + merge all case files
├── calibrate.py        is the judge right?
└── intensive.py        repeats, held-out split, honest counts

heldout/                cases the fixer never sees
docs/                   guides: writing cases, providers, stretch goals
results/                one JSONL per run
```

## The challenge (event brief)

| Level | Goal | Time |
|---|---|---|
| 1 | Meet the agent | 15 min |
| 2 | Write the tests | 45 min |
| 3 | Build the judge | 30 min |
| 4 | Fix it and prove it | 30 min |
| ⭐ | Bonus: tracing, model shoot-outs, red-teaming | any time left |

<details>
<summary><strong>Level 1 — Meet the agent</strong></summary>

1. Skim [agent/data/policies.md](agent/data/policies.md) — the file the tools actually read (`data/` is a mirror). That's what the bot should know.
2. Ask it a few questions with `uv run python -m agent.agent "..."`.
3. Run the starter suite: `uv run python -m evals.run --label baseline`.

**Done when:** you see a scorecard. (➖ means "not scored yet".)
</details>

<details>
<summary><strong>Level 2 — Write the tests</strong></summary>

1. Implement any missing check in [evals/checks.py](evals/checks.py) and add at least one of your own.
2. Add 15+ cases to [evals/cases.jsonl](evals/cases.jsonl) — see [docs/writing-cases.md](docs/writing-cases.md).
3. `uv run python -m evals.merge_cases` before you call it done.

**Done when:** 20+ cases, no ➖ in the Checks column, merge exits 0.
</details>

<details>
<summary><strong>Level 3 — Build the judge</strong></summary>

1. Complete the TODO in [evals/judge.py](evals/judge.py); the rubric is [evals/rubric.md](evals/rubric.md).
2. Re-run the suite and read 3–4 of the judge's reasons. Do you agree?
3. Is one score enough? A customer, a support manager and a lawyer would judge the same answer differently. Pick the perspectives that matter and decide how to measure each — a check, the judge, or a number.
4. Hand-label 8 answers with `evals/calibrate.py` and report agreement.

**Done when:** every case with an `expected` field is scored, and you can state your judge's agreement with your own labels.
</details>

<details>
<summary><strong>Level 4 — Fix it and prove it</strong></summary>

1. Pick a failure. Change **one thing**: the [system prompt](agent/system_prompt.md), a [tool](agent/tools.py), or the model.
2. Re-run and compare:

```bash
uv run python -m evals.run --label fix-1
uv run python -m evals.compare results/<baseline>.jsonl results/<fix-1>.jsonl
```

Watch for fixes that break something else — and remember not every fix belongs in the prompt.

**Done when:** the comparison shows at least one 🟢 fixed and no 🔴 broke, or you can explain why the trade was worth it.
</details>

## Team workflow

Six people, one file each — concurrent edits to `cases.jsonl` and `checks.py` are the bottleneck, not writing cases.

- **One case file per person**, ids prefixed by your area (`ord-`, `pol-`, `saf-`).
- **`merge_cases` before you push.** It catches duplicate ids and unknown check types that would otherwise show up as silent gaps.
- **Only one person edits `agent/`**, and one change at a time — otherwise you can't attribute the delta.
- **Only one machine runs the suite.** Several laptops hitting one Ollama instance queue up and look like flakiness.

## Demo (3 min)

- Your scorecard **before and after**
- One **interesting failure**, and why it happened
- **Do you trust your judge?** Why or why not — with the agreement number
- **Which metrics did you choose**, and what did each one reveal?

## Stuck?

| Problem | Try |
|---|---|
| Connection error | `docker compose ps`, check `.env` |
| Too slow | `--only <case-id>`, `--no-judge`, or a hosted model |
| Model ignores tools | Normal for small models — that's a finding, put it in a test |
| Judge and checks disagree | Report it, don't average it — that's the interesting case |
| Merge refuses to write | Read its errors: it names the file and line |

## Credits

Built at **Judge the Agent**, The Friendly Data Meetup London, 4 November 2026, on the challenge material from [dl-lim/friendly-meetup-hackathon](https://github.com/dl-lim/friendly-meetup-hackathon). The harness, cases, tooling and results in this fork are the team's work.

README structure inspired by [awesome-readme](https://github.com/matiassingers/awesome-readme).

MIT.
