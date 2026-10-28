# Paper citation and factual-claim audit — 28 October 2026

The former 17 cited UNVERIFIED entries were checked or retired as described
below. The active manuscript cites primary-source records only. Canonical ACL
BibTeX, including complete author lists, venues, pages and URLs, is retained in
`primary_bib/`. `scripts/prepare_paper_sources.py` retrieves those records and the
official ACL style. Existence/metadata verification does not verify every claim
that another document might attribute to a reference.

| Former key | Primary source and disposition |
| --- | --- |
| bowman2015snli | [ACL D15-1075](https://aclanthology.org/D15-1075/); canonical metadata retained |
| williams2018mnli | [ACL N18-1101](https://aclanthology.org/N18-1101/); canonical metadata retained |
| yin2021docnli | [Findings 2021.435](https://aclanthology.org/2021.findings-acl.435/); canonical metadata retained |
| koreeda2021contractnli | [Findings EMNLP 2021.164](https://aclanthology.org/2021.findings-emnlp.164/); canonical author spelling retained |
| gardner2020contrast | [Findings EMNLP 2020.117](https://aclanthology.org/2020.findings-emnlp.117/); replaced incomplete author list |
| gururangan2018annotation | [ACL N18-2017](https://aclanthology.org/N18-2017/); canonical metadata retained |
| mccoy2019right | [ACL P19-1334](https://aclanthology.org/P19-1334/); canonical metadata retained |
| roark2020dakshina | [LREC 2020.294](https://aclanthology.org/2020.lrec-1.294/); full author list retained |
| devlin2019bert | [ACL N19-1423](https://aclanthology.org/N19-1423/); verified but no longer cited as the evaluated model |
| sanh2019distilbert | [Author preprint](https://arxiv.org/abs/1910.01108); verified, no longer cited as evaluated model |
| elyaniv2010foundations | [JMLR primary record](https://www.jmlr.org/papers/v11/el-yaniv10a.html); added volume, issue and pages |
| geifman2017selective | [NeurIPS proceedings](https://papers.nips.cc/paper/2017/hash/4a8423d5e91fda00bb7e46540e2b0cf1-Abstract.html); verified venue and authors |
| koehn2004significance | [ACL W04-3250](https://aclanthology.org/W04-3250/); canonical metadata corrects earlier venue wording |
| smith2007tesseract | [Author's paper hosted by the project](https://tesseract-ocr.github.io/docs/tesseracticdar2007.pdf); title, author, year and pages verified |
| bulatov2022midv2020 | [Author preprint](https://arxiv.org/abs/2107.00396); use explicitly identified 2021 preprint under bulatov2021midv2020 instead of an incompletely checked 2022 journal entry |
| icao9303 | [ICAO Part 4 catalogue](https://store.icao.int/en/machine-readable-travel-documents-part-4-specifications-for-machine-readable-passports-mrps-and-other-td3-size-mrtds-doc-9303-4); catalogue identifies eighth edition, 2021. Full standard PDFs were not accessible; no claim of newly verifying transliteration tables, date conventions or issuing regulations |
| efron1993bootstrap | [Publisher catalogue](https://www.routledge.com/An-Introduction-to-the-Bootstrap/Efron-Tibshirani/p/book/9780429246593) confirms the book but displays 1994 copyright rather than settling the earlier edition's 1993 year. Retired from the active bibliography; edition/year remains unresolved, not silently marked verified |

New model citation: [Conneau et al., ACL 2020.747](https://aclanthology.org/2020.acl-main.747/),
with canonical full author list. This supports architecture attribution, not the
provenance of our recovered weights.

## Claims corrected or removed

- Replaced DistilBERT and CPU/frozen-embedding training claims with saved XLM-R
  metadata, explicitly distinguishing metadata from authenticated execution.
- Removed universal assertions about Indian passports printing regional names.
  The benchmark's multi-script observations are synthetic design choices.
- Removed assertions that all configured romanisations are attested or that all
  transliteration tables were verified against ICAO. Human disagreement remains.
- Removed a mandatory ten-year passport-validity assertion. Temporal constraints
  describe generator construction; no new legal/issuing-rule determination is made.
- Removed the blanket statement that collecting real identity documents is unlawful.
- Removed the claim rendered-text error is necessarily a lower bound on real OCR.
- Removed unsupported clean-to-heavy model generalization and rule-unreachable claims.
- Historical OCR and Dakshina statistics are not carried into the revised paper's
  empirical tables without a new pinned evidence inventory.
- Clarified neutral versus unresolved, conditional kappa, retrospective policy
  analysis and the limits of zero-error bootstrap intervals.

## Release and submission sources

The [Dakshina distributor](https://github.com/google-research-datasets/dakshina)
states CC BY-SA 4.0. This is a source-specific observation, not legal approval
of a combined redistribution. The owner selected planned code/synthetic-data
release subject to licensing review; nothing is published by this revision.

The [ARR call](https://aclrollingreview.org/cfp) and
[author guidance](https://aclrollingreview.org/authors) were checked for the
ACL review preparation. Current long-paper content limit is eight pages;
limitations, ethics, references and appendices must be identified separately.
Actual submission also requires author-controlled OpenReview profiles and
service-policy eligibility; local document preparation cannot satisfy these.
