# CLAUDE.md — operational guidance for coding agents in this repo

Read this before touching anything. It is instructions, not a project summary;
the summary is in `README.md`.

## What this is and where it stands

KYC-NLI reformulates identity-document field verification as three-way
document-level NLI (entailment / contradiction / neutral) across five scripts.

**Current phase: Phase 0 complete, Phase 1 not started.** The generator, the
transliteration engines, the OCR noise model, the rule baseline and the
evaluation harness all work. There is no neural model. `src/kyc_nli/nli/` is
empty on purpose.

**The finding that governs every decision here:** the deterministic rule
baseline reaches 0.977 macro-F1 on noise-free input. Do not propose work that
improves clean cross-script matching — there is nothing to win. The contribution
lives under OCR corruption. See `docs/plan.md`.

## Setup and commands

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"      # .venv/bin/python on unix
```

| Task | Command |
| --- | --- |
| Tests | `.venv/Scripts/python -m pytest` |
| Lint | `.venv/Scripts/ruff check src tests` |
| Autofix lint | `.venv/Scripts/ruff check --fix src tests` |
| Types | `.venv/Scripts/mypy` |
| Generate the benchmark | `.venv/Scripts/kyc-nli generate --identities 200 --noise moderate` |
| Compare baselines | `.venv/Scripts/kyc-nli compare` |
| Full report | `.venv/Scripts/kyc-nli run-baseline rule_engine` |
| Look at real instances | `.venv/Scripts/kyc-nli inspect --language ru -n 3` |
| Noise ablation | `scripts/run_noise_ablation.ps1` |

Always run tests and lint before declaring a change done. Both are fast.

## HARD RULES — violations are bugs, not style preferences

- **Never commit anything under `data/`, `results/` (except `MANIFEST.md`), or
  `.env`.** They are gitignored; do not `git add -f` them.
- **Never commit real or real-looking identity data** — not in tests, not in
  fixtures, not in notebook outputs, not in docstrings, not in example strings.
  Synthetic only, from `kyc_nli.data.name_pools`. If you need a new example
  name, add it to the pool; do not invent a plausible-looking real record.
- **Never let `provenance.contains_real_pii` become True** without a decision
  record and an explicit conversation. A test enforces this.
- **Strip notebook outputs before committing.** `nbstripout` is installed;
  install the hook with `.venv/Scripts/nbstripout --install`.
- **Never hand-edit a file in `results/` or a `*.manifest.json`.** Regenerate it
  from its script. These are machine-written records; editing one silently
  breaks reproducibility.
- **Never hardcode a language code.** Iterate `load_languages()`. A sixth
  language must be addable by editing `configs/languages.yaml` plus a name pool
  and nothing else.
- **Every experiment must be reproducible from a config plus a seed**, via a
  command in `src/kyc_nli/cli.py`. If a number came out of a notebook, it does
  not go in the paper until it comes out of a script.
- **Never weaken `baselines/rules.py` to make a model look better.** It is
  deliberately built to win; that is what makes the comparison credible. If a
  rule seems unfair, add the ablation, do not delete the rule.
- **Never fabricate a citation, a transliteration table entry, or a standard's
  contents.** Anything not verified against the primary source is marked
  `UNVERIFIED` in-code (see `translit/tables.py`) and must stay marked until
  someone checks it.

## Where the ground truth lives

| Question | File |
| --- | --- |
| What do the labels mean? | `docs/label-definitions.md` |
| How is anything measured? | `docs/evaluation-protocol.md` |
| Why is it built this way? | `docs/decisions/` |
| What happens next, and what could sink it? | `docs/plan.md` |
| What is the data model? | `src/kyc_nli/schema.py` — read this first |

## Conventions actually in use

- **Layout:** src-layout, `src/kyc_nli/`, installed editable. Imports are
  absolute (`from kyc_nli.x import y`), never relative.
- **Typing:** `from __future__ import annotations` at the top of every module;
  modern generics (`list[str]`, `X | None`).
- **Data model:** pydantic v2 for anything serialised (`schema.py`); plain
  dataclasses for internal config objects that never hit disk.
- **Config:** YAML in `configs/`, loaded through a pydantic model. No config
  values inline in code.
- **Randomness:** every stochastic component takes an explicit seed and stores
  it. `random.Random(seed)` instances, never the module-level `random`.
- **Paths:** `pathlib.Path`, resolved against `repo_root()` — never against the
  shell's cwd.
- **Docstrings:** say *why*, not *what*. The reader can see what the code does.
  Where a design choice answers a reviewer objection, name the objection.
- **Line length:** 100. Ruff enforces `E, F, I, UP, B, SIM`.

## Common tasks

**Add a language** — add a block to `configs/languages.yaml`; add a `NamePool`
to `kyc_nli/data/name_pools.py`; add a `Script` member and a `Transliterator`
subclass if the script is new; register it in `_ENGINE_CLASSES`; add a
transliteration test with a case that has a known-correct answer. Nothing else
should need to change; if it does, that is a bug in the abstraction.

**Add a baseline** — implement `predict(self, instance) -> Prediction` with a
`name` class attribute; register it in `kyc_nli/baselines/__init__.py::BASELINES`.
It appears in `kyc-nli compare` automatically.

**Add a phenomenon to the benchmark** — add a generator method returning a
contrast group, call it from `InstanceGenerator.generate`, give every instance a
distinct `phenomenon` tag and a real `rationale`. Then run
`kyc-nli inspect --phenomenon <tag>` and read the instances before trusting the
metrics.

**Run an ablation** — regenerate with a different `--noise` preset or generator
config into a distinct output path, then `kyc-nli compare --dataset <path>`.
Never overwrite an existing dataset in place.

**Regenerate a results table** — delete the file and re-run its command. Do not
edit it.

## Ask before deciding alone

Bring these to the project owner rather than resolving them yourself:

- Anything that changes **label semantics** (`docs/label-definitions.md`),
  especially the CONTRADICTION/NEUTRAL boundary. Changing it invalidates every
  dataset generated so far.
- Anything that changes the **evaluation protocol** — metrics, splits, noise
  levels, what counts as a baseline. Old numbers stop being comparable.
- Anything touching **data licensing or release**: what may be redistributed
  from MIDV, Dakshina or Wikidata, and whether the benchmark is publishable.
- Whether to **drop or reframe a claimed contribution**. The Phase-0 finding
  already forced one reframing; further ones are the owner's call, not yours.
- Adding a **heavy dependency**. The dev machine has 8 GB RAM and no CUDA GPU;
  anything that does not run on CPU belongs behind an optional extra and runs on
  Colab/Kaggle.
