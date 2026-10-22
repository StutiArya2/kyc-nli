# M2 — What real romanisation data showed

**Date:** 2026-09-06 · **Corpus:** Dakshina v1.0 (Google Research, CC BY-SA 4.0)
· **Reproduce:** `kyc-nli fetch-dakshina` then `kyc-nli translit-eval`

The roadmap said "replace the embedded name pools with Dakshina". That turned out
to be the *less* valuable use of the corpus, and this document explains what we
did instead and what it found.

## Why the plan changed

Dakshina's lexicons are general Wikipedia vocabulary, not a name list. Proper
nouns are in there but unlabelled, and the corpus is lowercase throughout, so
there is no signal to filter names on. Swapping it in as a name pool would have
produced a benchmark of ordinary words pretending to be surnames.

What Dakshina *does* have is the thing this project's central claim rests on:
**romanisations written by human beings.** Native speakers were asked to type a
word in Latin script, so one native word carries several attested spellings
produced by different people.

That makes it the right instrument for two jobs the project actually needs.

---

## Finding 1 — The project's core premise is now measured, not asserted

The proposal claims romanisation is one-to-many, supported by three hand-picked
examples. It is now a measurement over ~30,000 words per language.

| language | native words | attested spellings | spellings per word | words with **more than one** spelling |
| --- | --- | --- | --- | --- |
| Hindi | 29,610 | 52,466 | 1.77 | **57.0%** |
| Tamil | 29,887 | 81,377 | 2.72 | **74.6%** |
| Bengali | 29,715 | 112,089 | 3.77 | **90.2%** |
| Urdu | 29,478 | 125,180 | 4.25 | **97.6%** |

> **Corrected 2026-10-21.** The *spellings per word* column used to read 1.79,
> 2.71, 3.67 and 4.20. Those were means over the 2,000-word test-split sample
> in `results/transliteration.md`, sitting in a row whose other columns are
> full-corpus counts -- so dividing the row's own numbers gave a different
> answer from the one printed (Bengali: 112,089 / 29,715 = 3.77, not 3.67). The
> column is now the full-corpus ratio, consistent with its row and with
> Figure 2 of the paper. Every other column was already full-corpus and is
> unchanged.

**In Urdu, 98% of words have more than one human romanisation, averaging 4.2
spellings each.** Any system that assumes one correct Latin form is wrong on
almost every Urdu word before it starts.

The ordering also confirms the reasoning in
[decision 0005](decisions/0005-indian-language-set.md), which was written before
this data was consulted: Hindi least ambiguous, then Tamil, then Bengali, with
Urdu worst because the script writes no short vowels. Predicting the ordering and
then measuring it is a stronger position than either alone.

---

## Finding 2 — A lexicon does not generalise. At all.

We attached a lexicon of attested spellings built from Dakshina's **train** split
and scored on the **test** split. The improvement was exactly **zero**, in every
language.

The reason: Dakshina's splits are word-disjoint. Measured overlap between train
and test native words:

| hi | ta | bn | ur |
| --- | --- | --- | --- |
| 0 | 0 | 0 | 0 |

This is correct dataset design, and it makes a point the project needs:

> A lookup table can only help with names it has already seen. Every new customer
> is a name it has not seen.

This is the sharpest argument yet for a learned model, and it comes from data
rather than from assertion. It also bounds what the rule baseline can ever be:
however large its lexicon grows, its performance on genuinely novel names is its
rule performance alone.

---

## Finding 3 — Engine performance against romanisations we did not choose

Previously, engine recall was measured against 40 hand-written pairs per language
that **we wrote ourselves** — a number that flatters us by construction. Scored on
Dakshina's held-out test split instead:

| language | any-recall | top1-recall | spelling-recall | mean variants emitted |
| --- | --- | --- | --- | --- |
| Hindi | 0.800 | 0.725 | 0.677 | 43 |
| Tamil | 0.833 | 0.662 | 0.516 | 29 |
| Bengali | 0.860 | 0.625 | 0.432 | 348 |
| Urdu | **0.295** | 0.146 | 0.116 | 9 |

> **Corrected 2026-10-21.** This table previously showed figures from an
> earlier engine version (Urdu any-recall 0.303). The numbers above are what the
> current code produces, reproducibly: `kyc-nli translit-eval` regenerates them
> exactly and matches `results/transliteration.md`. Every change is in the
> second or third decimal; no conclusion moves.

- **any-recall** — at least one attested human spelling is in our variant set
- **top1-recall** — the *most-attested* spelling is in our set. Stricter, and
  closer to what matters: what a holder is most likely to actually write
- **spelling-recall** — the fraction of all attested spellings we cover

Read the gap between columns. Bengali has the best any-recall (0.861) and among
the worst spelling-recall (0.440): the engine usually catches *one* of the ways a
Bengali word is written, and usually misses most of the others. Since we cannot
know in advance which spelling a given holder used, any-recall overstates real
performance and top1-recall is the honest headline.

Bengali also emits 324 variants per word to achieve that. Recall bought with
over-generation costs precision at match time.

### The 40-pair figures were too optimistic

| | hand-written pairs (old) | Dakshina test split (new) |
| --- | --- | --- |
| hi | 90% | 80.0% |
| ta | 92% | 83.3% |
| bn | 100% | 86.0% |
| ur | 98% | **29.5%** |

Urdu is the one that matters. The old 98% was measured against pairs whose
romanisations had been used to *build* the Urdu lexicon in the first place — a
mild but real case of fitting the baseline to its own test pool, exactly what
`CLAUDE.md` warns against. Against independent data it is 30%.

The benchmark's Urdu score moved from 0.823 to 0.781 macro-F1 as a result, which
is inside the confidence interval. The headline ablation is unchanged. But the
*transliteration* figure was materially wrong and now is not.

---

## Two real bugs this exposed

**1. ICAO X-codes are MRZ encoding, not romanisation.**
`translit/tables.py` rendered hamza carriers with ICAO's X-prefixed codes, so
آئرلینڈ became `XAAYRLYND` where every human wrote `IRELAND`. No person writing
their own name in Latin script has ever written `XAA`. Those codes belong in an
MRZ generator, not in a matcher. The table now gives the human rendering, with a
comment saying why it must not be changed back.

This was flagged `UNVERIFIED` in the source since the file was written. The flag
was right.

**2. Perso-Arabic vowel letters were being read as consonants only.**
In Urdu, ی and و each serve as *both* a consonant and a long vowel, and the script
does not distinguish the two. Reading them as consonants only gave `AAYYN` where
people wrote `AAYEEN`, `AAIEEN`, `AAOIN` — the letters were present, we were
refusing to read them as vowels.

Adding that one linguistic fact took Urdu any-recall from **0.086 to 0.303** at
the time (0.295 in the current engine, after the `canonical()` fix below), a
3.5× improvement, at a cost of 9 variants per word.

**A third issue, found while fixing the second:** the vowel readings broke
`canonical()`, which the generator uses to decide what Latin the *document*
prints — صدیقی started rendering as `SDAIQAI` instead of the attested `SIDDIQUI`.
Recognition and generation are different jobs: the variant set should be generous
(accept what a holder might write), the printed form conservative (never print a
guess). `canonical()` now consults only the attested lexicon.

---

## What this does and does not license

**Can now be claimed, with a citation:**
- Romanisation of Indian-language names is one-to-many, in 57–98% of words
  depending on language, averaging 1.8–4.2 spellings per word.
- A romanisation lexicon provides no benefit on unseen words.
- Our rule-based engines recover the most-attested human spelling 63–73% of the
  time for Hindi, Tamil and Bengali, and 15% of the time for Urdu.

**Cannot be claimed:**
- That these are *name* statistics. Dakshina is general vocabulary. Names may be
  more or less variable than ordinary words, and we do not know which.
- That the benchmark uses real linguistic data. It still uses the embedded pools.
  Dakshina measures the engines; it does not yet feed the generator.

## Still open

- **Names specifically.** Wikidata person labels (CC0) in these four scripts would
  give a name-shaped corpus. Not started.
- **Urdu is still weak at 0.295.** Short vowels are genuinely unwritten, so a rule
  engine has a ceiling here. This is the strongest single case in the project for
  a learned model, and it should be called out in the paper rather than hidden.
- **Bengali over-generates** at 324 variants per word. Worth measuring what that
  costs in false matches.
