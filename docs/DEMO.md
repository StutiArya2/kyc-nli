# How to demo this

One command, about a minute, no network and no GPU. Everything on screen is
computed at the moment it appears — nothing is pre-recorded, so if a number looks
wrong the system is wrong.

## The command

```powershell
cd "C:\Users\HP\Desktop\projects\NLP\kyc-nli"
.\demo.ps1
```

That is the whole thing. `demo.ps1` sets the console to UTF-8 (without it,
Windows PowerShell mangles Devanagari and Bengali) and runs the walkthrough.

If you would rather type it yourself:

```powershell
$env:PYTHONIOENCODING="utf-8"; .\.venv\Scripts\kyc-nli.exe demo
```

**Before the room:** widen the terminal to at least 100 columns and increase the
font size. The tables are drawn to fit the width they are given, and a narrow
window wraps them into mush.

### How long it takes, and where it pauses

Sections 1, 2, 3 and 5 are instant. **Section 4 takes 1-2 minutes** — it is
loading a 541 MB model and scoring every system for real. A spinner shows what
it is doing, so it will not look frozen, but do not stand there in silence: that
pause is the natural place to explain what "whole-group correct" means.

It is slower while training is running, because both compete for the same CPU.

The demo scores a seeded 300-instance sample rather than the full 1,050 split —
same story, a fifth of the wait. `kyc-nli compare` scores everything if anyone
asks for the full numbers; add `--sample 0` to the demo for the same.

## What the five sections say

Run `.\demo.ps1 -Step N` to show one section on its own.

### 1 — The problem
A real document from the benchmark, side by side: the Bengali (or Hindi, or
Tamil) zone and the English zone. **Zero characters in common.** Same card, same
person. Character matching calls it a mismatch and rejects a real customer.

> *"This is one document. The bank's system compares these two strings and
> rejects the customer."*

### 2 — Three answers, not two
One real instance of each label, with the reason it carries that label.

The NEUTRAL panel is the one to dwell on: the surname is on the card but the scan
is unreadable. That is not fraud, it is *don't know*, and it belongs with a human.

> *"Every system in production has two answers. The third one is the
> contribution."*

### 3 — How bad is it, really?
Measured on Dakshina — romanisations written by native speakers, not by us.
Hindi averages 1.8 spellings per word; **Urdu 4.3, with 98% of words having more
than one.**

> *"We didn't assume romanisation is ambiguous. We measured it, on someone
> else's data."*

Skipped automatically if Dakshina is not downloaded. To have it: `kyc-nli fetch-dakshina` (~2 GB, once).

### 4 — Head to head
The scoreboard, scored live on 1,050 held-out instances. Read the **"whole-group
correct"** column, not the headline: it is the fraction of minimal-pair groups
where *every* variant is right, and it is what separates real inference from
noticing that two strings look similar.

> *"Exact matching rejects 89% of genuine customers. The rule engine gets that
> to 9% — but it does it by sending 63% of everything to a human. The model gets
> the same job done sending 29%."*

The row that carries the argument is **"sent to a human"** read next to
**"whole-group correct"**:

| | whole-group correct | sent to a human |
| --- | --- | --- |
| rule engine | 0.31 | 63% |
| cross-encoder | 0.88 | 29% |

Nearly three times the whole-group accuracy for less than half the human
workload. Be straight about the one column where the model is *worse*: it
rejects 16.7% of genuine customers against the rule engine's 9.3%. The rule
engine buys that by abstaining instead of deciding — which is what the 63%
review load costs.

### 5 — The finding
The result that reframed the project. We built the strongest possible rulebook
**against our own idea** first. On a clean scan it scores 0.981 — there is nothing
for a model to win there. Under realistic scan damage it collapses to 0.361, and
it fails by *giving up*: at heavy noise it abstains on 79% of cases the document
actually decides.

> *"We tried to kill our own idea in week one. It survived, but only in the place
> we weren't originally looking."*

## Three questions you will get

**"Is that difference real, or noise?"**
Run it with the statistics on:

```powershell
.\demo.ps1 -Bootstrap 1000
```

Every macro-F1 gets a 95% confidence interval and every comparison a paired
bootstrap test. It adds about 20 seconds.

**"Your model just abstains less. Isn't that only a different threshold?"**
The sharpest question in the room, and it has a measured answer. Fix the error
rate instead of comparing operating points:

```powershell
.\.venv\Scripts\kyc-nli.exe risk-coverage
```

At a 5% automation-error budget the rule engine **cannot operate at any
threshold** — the best it manages is 5.2% error while sending 93% of traffic to a
human. The cross-encoder meets that budget at its own natural operating point,
28.6% review at 4.0% error, and meets a 2% budget at 35.5% review. (Thresholds
are chosen on the dev split and tested on the held-out split, so it is not tuned
to the data it is scored on — expect that question.)
The reason is in the curves: the rule engine's confidences say *which rule fired*,
not how likely that rule is to be right, so its risk–coverage curve is not even
monotone and there is nothing usable to threshold on.
Full write-up: `docs/m4-selective-prediction.md`.

**"Isn't this just synthetic data?"**
Yes, and say so plainly — real identity documents are illegal to collect. Then
say what is *not* synthetic: the romanisations are human-written (Dakshina), and
the OCR error rates are measured from Tesseract across five scripts, not guessed.
`docs/m1-ocr-calibration-findings.md` and `docs/m2-dakshina-findings.md`.

## If something goes wrong

| Symptom | Fix |
| --- | --- |
| Indic text shows as boxes or `?` | Use Windows Terminal, not the old console. `demo.ps1` already sets UTF-8. |
| Tables wrap badly | Widen the window past 100 columns. |
| "No benchmark on disk" | Harmless — it generates one on the spot, adds ~15s. |
| Section 3 skipped | Dakshina not downloaded. Fine to skip; say the numbers instead. |
| "cross_encoder is not trained yet" | Only if the checkpoint is missing. Sections 1–5 all still run without it. |
| A wall of red PowerShell text | You ran `kyc-nli.exe` directly rather than `demo.ps1`. The model prints its load report to stderr and PowerShell treats that as an error; `demo.ps1` handles it. |

**The demo never requires the neural model.** If the checkpoint is missing it
shows the baselines and says so. That is deliberate: a demo that depends on a
long training run having finished is a demo that fails in front of an audience.

## Deeper dives, if asked

**Run these from the repo root, and use the `.\.venv\Scripts\` prefix.**
`kyc-nli` is installed inside the virtual environment, not on the system
PATH, so a bare `kyc-nli ...` gives "not recognized as the name of a
cmdlet" — which is a bad thing to discover in front of a room.

```powershell
# Read actual benchmark instances, in any language
.\.venv\Scripts\kyc-nli.exe inspect --language ta -n 2

# Why these five languages
.\.venv\Scripts\kyc-nli.exe languages

# Full per-language and per-phenomenon breakdown
.\.venv\Scripts\kyc-nli.exe run-baseline rule_engine

# The engines against real human romanisations
.\.venv\Scripts\kyc-nli.exe translit-eval

# Review load at a fixed error rate, per system (milestone M4)
.\.venv\Scripts\kyc-nli.exe risk-coverage
```

If asked how any of it is verified: `docs/testing.md` — 409 tests, 87% statement
coverage, and the fifteen defects testing turned up, none of which moved
a published number.

## The slide deck

`docs/proposal/KYC-NLI-Mid-Review.pptx` — 11 slides covering the same ground.
Use the deck for the narrative and the terminal for the proof; running
`.\demo.ps1` live after slide 7 is worth more than any slide.
