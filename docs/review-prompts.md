# Prompts for KYC-NLI Proposal Review

Three copy-paste prompts. Each is designed to be run in a **fresh** conversation with
web search enabled, with `NLP review 1.pptx` attached.

**Why fresh sessions:** a model that helped shape the idea will defend it. Novelty and
literature audits only work adversarially.

**Shared context block** — paste this at the top of Prompt 1 and Prompt 2 if you are not
attaching the deck:

<details>
<summary>Project context block (expand to copy)</summary>

```
PROJECT: KYC-NLI — Document-Level Natural Language Inference for Identity Verification

CORE CLAIM: Reformulate identity-document verification as a 3-way document-level NLI
task (Entailment / Contradiction / Neutral) over pairs of extracted document fields,
replacing exact string matching.

PIPELINE: OCR extraction -> cross-script/transliteration handling -> document-level NLI
-> temporal & numerical consistency checking -> explainable E/C/N decision -> human
review routed for Neutral cases.

CLAIMED CONTRIBUTIONS:
1. 3-way NLI formulation for identity verification (vs. binary match/no-match)
2. Semantic field verification integrated with multilingual transliteration handling
3. Cross-field logical reasoning (temporal, numerical, contextual) instead of
   independent per-field validation
4. Robustness to OCR-induced errors via semantic inference
5. A new "KYC-NLI benchmark" with multilingual scenarios, minimal-pair contrast sets,
   and semantic consistency labels
6. Explainable decisions identifying supporting/conflicting fields, for KYC/AML audit

CLAIMED GAPS IN PRIOR WORK: vision-centric verification; exact-match dependence;
no cross-field reasoning; weak transliteration support; OCR-noise sensitivity;
no standardized semantic benchmark.

MOTIVATING EXAMPLES FROM THE PROPOSAL:
- Arabic name vs. its ICAO Latin transliteration share zero substrings -> exact match
  produces a false mismatch.
- Issue Year 1995 + Expiry 2035 + Template Era "2020 hologram" are individually valid
  but jointly impossible -> per-field matching misses it.
- OCR errors cascade across Visual Zone / MRZ / Barcode / form fields.
```

</details>

---

## Prompt 1 — Novelty Audit

**Run in:** a fresh session, web search ON. Attach the deck.

```
You are acting as a hostile Program Committee reviewer for a top-tier venue (ACL / EMNLP
/ Information Fusion). Your job is NOT to encourage me. Your job is to find the reasons
this proposal would be rejected, before a real reviewer does.

Attached is a research proposal: [PASTE CONTEXT BLOCK or attach NLP review 1.pptx]

Work through the following stages IN ORDER. Do not skip to recommendations.

STAGE 1 — CLAIM DECOMPOSITION
Restate the proposal as a numbered list of ATOMIC, falsifiable novelty claims. Each claim
must be phrased so that a single prior paper could refute it. Split any claim that bundles
a task formulation with a method with a dataset — those are three claims, not one.
If a stated contribution is not actually a novelty claim (e.g. "improves robustness"),
say so and either sharpen it or discard it.

STAGE 2 — PRIOR ART SEARCH (use web search; do not answer from memory)
For EACH atomic claim, search for prior work that already does it. Search at minimum:
  - ACL Anthology, arXiv, IEEE Xplore, Springer, Elsevier
  - Industry/non-academic prior art: ICAO Doc 9303, ISO/IEC 18013, MRZ check-digit and
    field-cross-validation logic already mandated in the standards, and commercial KYC
    vendor documentation (Onfido, Jumio, Regula, IDnow, Veriff)
  - Adjacent literatures that use different vocabulary for the same idea. Search these
    terms explicitly, because they are where this idea is most likely already solved:
    "document-level NLI" / DocNLI, "table-to-text entailment" (TabFact, INFOTABS,
    FEVEROUS), "fact verification" (FEVER lineage), "record linkage" and "entity
    resolution with LLMs", "cross-lingual name matching", "transliteration equivalence",
    "consistency checking in structured records", "form understanding" (LayoutLM,
    LiLT, Donut, DocVQA), "numerical reasoning over text" (DROP, FinQA).

For each claim, report a verdict from exactly this set:
  [ALREADY DONE]  — cite the paper that does it; the claim is dead as stated
  [DONE ADJACENTLY] — same technique, different domain; novelty is only the transfer
  [INCREMENTAL]   — a delta on existing work; state precisely how large the delta is
  [GENUINELY OPEN] — you searched and found nothing; say what you searched

Format as a table: Claim | Verdict | Strongest refuting/nearest work (full citation +
link) | One-line justification.

HARD RULE ON CITATIONS: every paper you cite must be one you actually located via search
in this session. Include a working link for each. If you believe relevant work exists but
cannot find it, write "SUSPECTED PRIOR ART, UNVERIFIED" and describe what to search for —
do NOT produce a plausible-looking citation. A fabricated citation makes this entire
audit worthless to me.

STAGE 3 — THE STRONGEST OBJECTION
State, in one paragraph, the single most damaging criticism a reviewer would make. Then
answer these specifically:
  a) Is "3-way NLI over ID fields" a genuine reformulation, or is it standard NLI applied
     to a new input with the labels renamed? What would have to be true for it to be a
     real reformulation?
  b) The Neutral class routes to human review. Is Neutral a principled semantic category
     here, or is it an abstention/confidence threshold wearing a semantic label? A
     reviewer WILL ask this. Can you name a field pair that is genuinely Neutral rather
     than merely low-confidence?
  c) Cross-field temporal/numerical consistency (issue date vs. expiry vs. template era)
     is expressible as deterministic rules over a small closed field schema. Why is an
     NLI model the right tool rather than a rule engine plus a lookup table of template
     eras? If a rule baseline gets 99% on this, the NLI contribution collapses. Argue
     both sides, then state which you find more convincing.
  d) Transliteration equivalence is a well-studied matching problem with strong
     non-NLI solutions. What does NLI add over a transliteration-aware string metric?
  e) Datasets of real identity documents are legally unobtainable. If the "KYC-NLI
     benchmark" is synthetic, what stops a reviewer from dismissing every result as
     an artifact of the generator that produced the data?

STAGE 4 — VERDICT AND REPAIR
  1. Novelty verdict: one of REJECT-AS-IS / MAJOR REVISION / MINOR REVISION / PUBLISHABLE,
     with the appropriate venue tier for the current framing.
  2. The 3 claims to DROP, and why keeping them weakens the paper.
  3. The 1-2 claims to make the CENTRAL contribution, and how to reframe the abstract
     around them.
  4. 3-5 concrete pivots or sharpenings, each with: what changes, why it raises novelty,
     estimated added effort in person-weeks, and what new risk it introduces. Rank them
     by (novelty gained) / (effort + risk).
  5. The minimum experiment that would prove the central claim. Specify: baselines that
     must be beaten (include the strongest non-neural baseline — a rule engine plus
     transliteration-aware fuzzy matching — not just a weak string-equality baseline),
     metrics, and the result that would falsify the claim.

TONE: Blunt. No praise sandwiches, no "this is a promising direction". If the honest
assessment is that the core idea is a repackaging of existing work, say that in the
first line and spend the rest of the response on what to do instead.
```

---

## Prompt 2 — Literature Review Audit

**Run in:** a fresh session, web search ON. Attach the deck (slides 4–16 are the review).

```
You are auditing the literature review section of a research proposal before submission.
Attached/pasted is a 12-paper literature review plus a comparative analysis table for a
project on document-level NLI for identity (KYC) verification.

[ATTACH NLP review 1.pptx — slides 4 through 17]

Perform four passes. Report each separately.

PASS 1 — CITATION VERIFICATION (do this first; use web search on every entry)
For each of the 12 papers, verify by searching that:
  - the paper exists
  - title, author list, year, and venue are all correct as stated
  - the venue is real and correctly named, and the year is consistent with that venue's
    actual publication cycle
  - the reported quantitative results (EER, F1, accuracy, dataset sizes) match the paper

Output a table: # | Title as cited | VERIFIED / WRONG METADATA / CANNOT VERIFY /
DOES NOT EXIST | Correction | Source link.

Pay particular attention to entries that are hard to verify or dated in the future
relative to their venue's cycle — a citation that cannot be verified is a submission
risk regardless of whether it is real. Flag anything where the deck states a specific
number that you cannot confirm from the source, and separately flag any entry whose
row in the deck is missing fields other rows have (e.g. an omitted Evaluation Metrics
row), since a reviewer reads that as the author not having read the paper.

If any citation does not check out, say so plainly. Do not smooth over it.

PASS 2 — COVERAGE GAPS
Identify seminal or directly-relevant work that is MISSING. Search deliberately in each
of these areas and report what should be added, with citation and a one-line reason:
  a) Document-level NLI foundations: DocNLI, ANLI, MNLI/XNLI, and any NLI-over-structured-
     data work (TabFact, INFOTABS, FEVEROUS)
  b) Identity-document datasets the project could actually use: MIDV-500, MIDV-2019,
     MIDV-2020, MIDV-Holo, DocXPand-25k, and any successor. This matters because the
     proposal promises a benchmark and must position it against existing ones.
  c) Document understanding / OCR-noise-robust models: LayoutLM family, LiLT, Donut,
     TrOCR, and post-OCR correction literature (ICDAR post-OCR competitions)
  d) Transliteration resources rather than surveys: the Dakshina dataset, the NEWS
     transliteration shared tasks, ICAO Doc 9303 Part 3 transliteration rules
  e) Entity resolution / record linkage with LLMs beyond the single industry paper cited
  f) Fact verification with evidence retrieval and explainability (FEVER lineage)
  g) Selective prediction / abstention and calibration — this is the actual literature
     behind the proposal's "Neutral -> human review" mechanism, and it is currently
     absent
  h) Anything from 2025-2026 that has already attacked this exact problem

For each gap, state the consequence: which of the proposal's claimed contributions
becomes indefensible if this work is not cited and distinguished.

PASS 3 — CRITICAL ACCURACY OF THE "RESEARCH GAP" COLUMN
The review assigns each paper a "Research Gap" and a "How My Idea Improves" line. For
each, judge whether the stated gap is a REAL limitation of that paper or an ARTIFACT of
comparing a paper to a task it never claimed to address. Criticizing a computer-vision
forgery-detection paper for having "no semantic text layer" is the latter, and a reviewer
will read it as strawmanning.

Output: # | Gap as stated | FAIR / STRAWMAN / OVERSTATED | Rewritten fair version.

Also assess: are these 12 papers a coherent related-work set, or several disconnected
clusters (ID forgery detection / KG validation / general NLI / surveys) with no through-
line? If the latter, propose a thematic reorganization into 3-4 subsections with a
narrative that arrives at the research gap, and tell me which papers to cut. A review
that reads as 12 unrelated summaries signals breadth-without-synthesis.

PASS 4 — WRITE-UP QUALITY
  - Is the ratio of surveys to primary papers appropriate? (There are 2-3 surveys here.)
  - Is the field balanced, or is one sub-area over-represented relative to its
    importance to the argument?
  - Does the comparative table's final column make claims the proposal has not yet
    earned (asserting improvement over methods that have not been run)? Rewrite any
    such cell as a hypothesis rather than a result.
  - Give the 5 highest-priority edits, ordered, with estimated effort each.

Ground every claim in a source you actually retrieved this session. Where you cannot
verify, write CANNOT VERIFY rather than guessing.
```

---

## Prompt 3 — Project Plan Verification + Repo Scaffold

> **Gap to close first:** the deck contains the problem statement, objectives, literature
> review, and gap analysis — but **no methodology, timeline, evaluation protocol, or
> deliverables schedule**. There is no "final project plan" to verify yet. Write a 1-2
> page plan covering the bracketed items below before running this prompt, or the review
> half will have nothing to bite on.

**Run in:** Claude Code, in the directory you want the repo in.

```
Two tasks, in order. Do not start Task B until Task A is complete and I have responded.

===== TASK A: STRESS-TEST THE PROJECT PLAN =====

Here is the plan for KYC-NLI, a document-level NLI framework for identity verification
(see NLP review 1.pptx for full context):

[PASTE YOUR PLAN — it must cover:
  - Methodology: model architecture, how OCR / transliteration / NLI / consistency-
    checking modules connect, and what is trained vs. off-the-shelf vs. rule-based
  - Data: exact source of every document used, real or synthetic; if synthetic, the
    generator and how realism is validated
  - Experimental protocol: baselines, metrics, ablations, train/dev/test splits
  - Timeline: milestones with dates
  - Compute: what hardware you have access to
  - Deliverables: paper, benchmark release, code, demo]

Evaluate the plan against the following. Be specific and quantitative; "consider adding
more data" is not useful feedback.

1. FEASIBILITY GATES — for each, answer GREEN / AMBER / RED with justification:
   a) DATA. Real identity documents cannot be legally collected, shared, or published.
      What exactly is the data source? If synthetic, which generator, and how is realism
      validated? Check what MIDV-500/2019/2020, MIDV-Holo, and DocXPand-25k actually
      contain and whether their licenses permit this use and permit publishing derived
      annotations. State plainly whether the proposed benchmark is legally releasable.
      If it is not, the benchmark contribution is dead — say so now, not in month five.
   b) LABELS. Who assigns the E/C/N gold labels, by what protocol? What inter-annotator
      agreement is required for the benchmark to be credible, and is the labeling budget
      realistic given the annotator count available?
   c) COMPUTE. Given the stated hardware, is the largest proposed model trainable in the
      time available? If not, name the largest model that is, and what is lost.
   d) SCOPE. Which parts of the pipeline are actually research contributions and which
      are engineering plumbing that could be swapped for an off-the-shelf component?
      Recommend cutting anything that costs weeks and contributes no novelty. Be
      aggressive here — OCR and transliteration both have mature off-the-shelf options.
   e) EVALUATION. Are the baselines strong enough to make a win meaningful? A rule engine
      plus transliteration-aware fuzzy matching MUST be one of them. Adding a
      string-equality baseline that the method trivially beats will be read as
      strawmanning.
   f) ETHICS/LEGAL. GDPR/DPDP implications, PII handling, whether IRB or institutional
      review is needed, and what the paper must state about data provenance.

2. CRITICAL PATH. Give the dependency ordering of milestones and identify the single
   task whose slippage sinks the timeline. Then state the earliest point at which a
   go/no-go signal is available on the central claim, and design a 2-week pilot that
   produces that signal. If the pilot can be pulled earlier, restructure the plan to
   do so.

3. RISK REGISTER. Top 5 risks as a table: Risk | Likelihood | Impact | Early warning
   sign | Mitigation | Fallback contribution if it fires. Every risk needs a fallback —
   what is the publishable result if the main claim fails?

4. REVISED PLAN. Rewrite the timeline with the above folded in. Mark any milestone you
   consider unachievable and say what you replaced it with.

Stop here. Show me Task A output and wait for my response before continuing.

===== TASK B: BUILD THE REPOSITORY =====

Only after I approve Task A. Create the repo in the current directory.

STRUCTURE — create directories with a .gitkeep and a one-line purpose comment; do NOT
write implementation code or stub modules yet:
  README.md, CLAUDE.md, LICENSE, .gitignore, requirements.txt (or pyproject.toml),
  .env.example
  configs/         experiment configs, YAML, one per experiment
  data/            raw/ interim/ processed/ external/  -- ALL gitignored, never committed
  docs/            proposal/ (the pptx), literature/, decisions/
  notebooks/       exploratory only, numbered
  src/kyc_nli/     ocr/ transliteration/ nli/ consistency/ explain/ evaluation/
  tests/
  scripts/         entry points for reproducing each experiment
  results/         metrics + figures, gitignored except a manifest

README.md must contain, in this order:
  1. One-sentence description, then a 3-sentence "what problem does this solve" for a
     reader who has never heard of KYC or NLI
  2. The three motivating examples from the proposal (cross-script name, jointly
     impossible date triple, cascading OCR failure) as a table showing what exact
     matching returns vs. what the system should return
  3. The E/C/N label definitions with 2 worked examples each, including the decision
     boundary between Contradiction and Neutral -- this is the part everyone gets wrong
  4. Architecture diagram as a mermaid flowchart, OCR through to decision + human review
  5. Installation, from a clean machine, with exact commands
  6. Quickstart: smallest command producing a real output
  7. Data section: where every dataset comes from, its license, and an explicit statement
     that no real identity documents are stored in this repo
  8. Reproducing the experiments: one command per table/figure in the paper
  9. Repository layout with a one-line purpose per directory
 10. Project status and roadmap with checkboxes
 11. Citation (BibTeX), license, contact
Write it so a new collaborator can be productive without asking a question. Do not
document code that does not exist yet -- mark unbuilt sections "Not yet implemented".

CLAUDE.md must be operational guidance for a coding agent working in this repo, not a
project summary. Include:
  - Project one-liner and the current phase
  - Setup and environment commands, and how to run tests, lint, and the full pipeline
  - Code conventions actually in use: package layout, typing, config handling, logging,
    random-seed policy, how experiments are recorded
  - HARD RULES, stated as prohibitions:
      * never commit anything under data/, results/, or .env
      * never commit real or real-looking identity data, including in tests, notebook
        outputs, docstrings, or fixtures -- synthetic fixtures only
      * strip notebook outputs before committing
      * never edit a results file by hand; regenerate it from its script
      * every experiment must be reproducible from a config plus a seed
  - Where the ground truth lives: label definitions, the evaluation protocol, and the
    decision log in docs/decisions/
  - Common tasks with the exact command for each (add a dataset, add a baseline, run an
    ablation, regenerate a results table)
  - What to ask me about rather than deciding alone: anything touching label semantics,
    the evaluation protocol, or data licensing

.gitignore must cover Python, Jupyter, venvs, IDEs, OS files, and explicitly data/,
results/, .env, and common image/PDF extensions at the repo root as a guard against
accidentally committing document scans.

Then: git init, an initial commit, and print the exact commands for me to create the
GitHub remote and push. Do NOT create a GitHub repo, add a remote, or push anything --
I will run those myself. Tell me whether you recommend public or private given the
data-licensing findings from Task A, and why.
```

---

## Suggested order

Run **1** before **2** before **3**. The novelty audit may kill or redirect claims, which
changes which literature matters, which changes what the plan and repo need to support.
Building the repo first means rebuilding it.
