# 0003 — The five-language set: en, ru, ar, hi, zh

**Status:** accepted · **Date:** 2026-09-06

## Context

The project claims multilingual transliteration handling. "Multilingual" with
three European languages would be trivially attackable. Five languages was the
target; which five is a research decision, not a convenience one.

## Decision

| code | script | why it is in the set |
| --- | --- | --- |
| en | Latin | Control. Isolates how much of any gain is cross-script transfer versus ordinary lexical variation. |
| ru | Cyrillic | ICAO Doc 9303 fixes a **normative** Latin transliteration, and the VIZ/MRZ pair on a single Russian passport shares zero characters. Errors are adjudicable against a standard, not a matter of opinion. |
| ar | Arabic | RTL, OCR-dropped diacritics, and genuinely **one-to-many** romanisation (Mohammed / Muhammad / Mohamed). Tests whether romanisation is treated as set-valued. |
| hi | Devanagari | **No normative table exists.** The same holder romanises their own name differently on different forms. This is the case a lookup table cannot solve and a learned model plausibly can — the strongest argument for the method. |
| zh | Han | Name-order inversion, no whitespace, and heavy homophony after Pinyin. Produces the **opposite** error to Arabic: false matches rather than false mismatches. |

Each has a public, licensable source of native/Latin name pairs: Dakshina
(CC BY-SA 4.0) for hi, Wikidata person labels (CC0) for ar/ru/zh, MIDV-2020 for
ru document templates.

Tamil (Taml) is the documented swap-in candidate — Dakshina covers it and it
adds a second Brahmic script — and is deliberately not enabled in v1.

## Consequences

- No language code is hardcoded anywhere. `configs/languages.yaml` is the single
  source of truth; adding a sixth language is a config block plus a name pool.
- Per-language macro-F1 is a mandatory reporting axis. A headline driven by
  English says nothing about the cross-script claim.
- Dataset splits are stratified by language. An earlier unstratified split put
  100% of the test set in Arabic and made the per-language table meaningless.
