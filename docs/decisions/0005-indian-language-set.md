# 0005 — The language set is Indian: en, hi, ta, bn, ur

**Status:** accepted · **Date:** 2026-09-06 · **Supersedes:** [0003](0003-five-language-set.md)

## Context

Decision 0003 chose en / ru / ar / hi / zh on the grounds of maximum script
diversity. That set was globally spread but domain-incoherent: five countries,
five document regimes, and no single deployment in which all five occur. It also
required scraping Wikidata for three of the five languages, giving a weak data
story for a project whose headline contribution is a benchmark.

The project owner asked for Indian languages.

## Decision

The active set is **en, hi, ta, bn, ur** — Latin, Devanagari, Tamil, Bengali and
Perso-Arabic. Five distinct scripts, all five official Indian languages, all five
appearing on documents issued by one state.

This is not a narrowing of the contribution. It is a sharpening, for four
reasons.

**1. The cross-script pair becomes in-document rather than cross-record.**
Indian identity documents print the holder's name in English *and* in a regional
script on the same physical card. The premise for a cross-script entailment
judgement is therefore a single document, which is exactly the "document-level
NLI" framing the proposal claims. The old set had to compare a Russian passport
against a separately-obtained record.

**2. One licence covers four of the five languages.** The Dakshina dataset
(Google Research, CC BY-SA 4.0) ships paired native-script and romanised
lexicons for Bengali, Hindi, Tamil and Urdu. One download replaces the embedded
pools for the entire non-English set. Under 0003, three of five languages
depended on ad-hoc Wikidata extraction with no romanisation pairing.

**3. The set now contains the cases a lookup table cannot win.** This matters
more than script diversity, because the Phase-0 finding is that a rule engine is
already at ceiling on clean input.

| language | romanisation | why it is here |
| --- | --- | --- |
| en | identity | Control. Every Indian document carries an English zone, so this is the zone the others are compared *against*, not an artificial baseline. |
| hi | non-normative | No authority fixes the answer; the same holder romanises their own name differently on different forms. |
| ta | non-normative | **The script does not mark voicing at all.** க is K or G, ச is CH or S, ப is P or B, with equal legitimacy. A lookup table cannot be right even in principle, because there is no single right answer to look up. |
| bn | non-normative | Inherent vowel nearer /o/ than /a/ (BASU/BOSE), no /v/, and the ya-phala shares a letter with /dʒ/ (BANDYOPADHYAY/BANDOPADHYAY). Tests whether a model learns a *script-level alternation* rather than a per-name mapping. |
| ur | partial | Short vowels are not written, so the script yields a consonant skeleton (SDYQY) and the vowels come from a lexicon (SIDDIQUI). The only partially-normative member, which makes it the internal contrast case. |

Under 0003, three of five languages (en, ru, zh) had *fully normative* or
near-deterministic romanisation. Under 0005, four of five are non-normative or
partial. The set is now concentrated on the regime where the project's claim
could be true.

**4. It matches the one production system in the literature review.** SGER
(ACL 2026) is Indian KYC name matching at 250M-user scale, and it is the closest
prior work in the deck. Sharing its domain makes the comparison direct instead of
analogical, and its stated limitation — binary labels, no neutral class, names
only — is precisely what this project extends.

### `normative` becomes three-valued

Urdu forced this. ICAO Doc 9303 fixes the consonants but the script writes no
short vowels, so the standard determines *part* of the answer. A boolean would
either overstate what the table gives (True) or discard a real constraint the
baseline is entitled to use (False). `Romanisation.normative` is now
`full | partial | none`, with a validator accepting the old boolean form.

### What is given up, and why it is acceptable

- **The fully-normative contrast case.** Russian was the one language where ICAO
  fixes exactly one correct rendering, which made errors adjudicable against a
  standard rather than a matter of opinion. Urdu partially replaces this. Russian
  is *retained in code* — pool, transliterator and tests all still work — so the
  contrast experiment costs a config edit, not a rewrite.
- **The false-*match* phenomenon.** Chinese romanisation collapses distinct names
  onto the same Pinyin, the mirror image of the Arabic error. Also retained in
  code. Bengali partially covers it: the A/O and B/V alternations over-generate
  enough that distinct names can collide.
- **Global framing.** "Multilingual KYC" becomes "Indian KYC". This is a gain.
  Narrow and well-motivated beats broad and thin, and no reviewer can claim the
  scripts were cherry-picked for ease — Tamil, Bengali and Urdu are low-resource
  and genuinely hard.

## Consequences

- `configs/languages.yaml` is rewritten; `ru` and `zh` move to a commented block.
- `name_pools.POOLS` holds the active five; `RETAINED_POOLS` holds ru and zh.
- Name pools became `(native, attested_latin)` **pairs**, mirroring Dakshina's
  shape. Deriving the document's own Latin from the transliterator had printed
  SARM for शर्मा and CHUBRAMANIYAN for சுப்ரமணியன்; a document prints the
  attested spelling, and the transliterator's job is to *recognise* variants at
  match time, not to decide what the document says.
- `get_transliterator` now dispatches on **script and language**. Urdu and Arabic
  share a script but need different tables; dispatching on script alone silently
  gave Urdu names the Arabic treatment, dropping every U+06A9 and U+06CC.
- New engines: `TamilTransliterator`, `BengaliTransliterator`,
  `UrduTransliterator`, plus a shared `BrahmicTransliterator` base.
- Measured romanisation recall against the pools: en 100%, hi 90%, ta 92%,
  bn 100%, ur 98%. Regression floors are asserted in `tests/test_translit.py`.
  **The residual is a finding, not a defect to tune away** — the misses need
  schwa *epenthesis* (अग्रवाल → AGARWAL), monophthongisation (नायर → NAIR) or
  Grantha conjunct handling (லட்சுமி → LAKSHMI). Closing them with per-name rules
  would be fitting the baseline to the test pool.
- The Phase-0 finding survives the change and sharpens: exact matching is *worse*
  on Indic scripts (0.371 vs 0.425 macro-F1 clean, false-mismatch 67% vs 55%),
  because Indic scripts share even fewer characters with Latin than Cyrillic does.
