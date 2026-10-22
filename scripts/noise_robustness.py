"""Score every system at every noise level, on the SAME held-out documents.

    python scripts/noise_robustness.py          # ~15 min on a CPU, most of it the model

Why this exists, and why it does not reuse the abl_* datasets
-------------------------------------------------------------
The cross-encoder was trained once, at moderate noise. The question a reviewer
asks next is how it holds up when the capture is better or worse than that. The
obvious way to answer it -- score the model on the existing abl_{clean,light,
moderate,heavy} test splits -- is wrong, and silently so:

  * Those datasets were generated before the identity-level split fix. They carry
    no identity_id, so their splits fall back to the contrast group and leak.
  * Worse, 253 of their 616 test instances (41%) share a document number with
    the model's own training set. Scoring the model there measures memorisation.

The rule baselines are untrained, so their abl_* numbers stand. A trained model
must never be scored on those files.

What this does instead: regenerate synth_v0's exact config -- 200 identities per
language, seed 20260906 -- at each noise preset. The generator's identity RNG is
independent of the noise preset, so every level yields the SAME 1,050 held-out
instances (same ids, same gold labels, same document numbers, zero overlap with
training) and differs ONLY in the OCR damage. Every level is asserted against
synth_v0.test below rather than assumed. That is a controlled experiment: the
documents are held fixed and only the corruption varies.
"""

from __future__ import annotations

import json
import sys
import time

from kyc_nli.baselines import available_systems
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import load_instances, save_instances, split_by_identity
from kyc_nli.evaluation import (
    DEFAULT_RESAMPLES,
    evaluate,
    paired_bootstrap,
    review_load_at_error,
)
from kyc_nli.languages import load_languages, repo_root
from kyc_nli.schema import Field

LEVELS = ("clean", "light", "moderate", "heavy")
#: The training run's config. Changing either breaks the "same documents" claim.
IDENTITIES = 200
SEED = 20260906
TRAINED_AT = "moderate"


def _doc_numbers(instances) -> set[str]:
    return {
        o.clean_value
        for i in instances
        for o in i.premise
        if o.field is Field.DOCUMENT_NUMBER and o.clean_value
    }


def _test_split(level: str) -> list:
    """The held-out split at ``level``, generated once and cached on disk."""
    root = repo_root()
    path = root / "data" / "processed" / f"noise_{level}.test.jsonl"
    if path.exists():
        return load_instances(path)
    config = GeneratorConfig(
        languages=tuple(load_languages()),
        identities_per_language=IDENTITIES,
        noise_preset=level,
        seed=SEED,
    )
    test = split_by_identity(InstanceGenerator(config).generate())["test"]
    save_instances(test, path)
    return test


def main() -> int:
    root = repo_root()
    reference = load_instances(root / "data" / "processed" / "synth_v0.test.jsonl")
    train = load_instances(root / "data" / "processed" / "synth_v0.train.jsonl")
    ref_ids = {i.id for i in reference}
    ref_gold = {i.id: i.label for i in reference}
    train_docs = _doc_numbers(train)

    systems = available_systems()
    if "cross_encoder" not in systems:
        print("No trained cross-encoder checkpoint; scoring the baselines only.")

    payload: dict = {
        "note": (
            "Same 1,050 held-out instances at every level; only the OCR damage "
            f"differs. The cross-encoder was trained at {TRAINED_AT!r} noise only."
        ),
        "seed": SEED,
        "identities_per_language": IDENTITIES,
        "trained_at": TRAINED_AT,
        "levels": {},
    }

    for level in LEVELS:
        test = _test_split(level)

        # The whole experiment rests on these three holding. Check, don't trust.
        assert {i.id for i in test} == ref_ids, f"{level}: held-out instances differ"
        assert all(i.label is ref_gold[i.id] for i in test), f"{level}: gold labels differ"
        overlap = _doc_numbers(test) & train_docs
        assert not overlap, f"{level}: {len(overlap)} test documents appear in training"

        print(f"\n== {level} ({len(test)} instances, 0 shared with training) ==")
        payload["levels"][level] = {}
        level_preds: dict[str, list] = {}
        for name, cls in systems.items():
            started = time.time()
            model = cls()
            batched = getattr(model, "predict_all", None)
            preds = batched(test) if callable(batched) else [model.predict(i) for i in test]
            level_preds[name] = preds
            report = evaluate(name, test, preds, bootstrap=DEFAULT_RESAMPLES)
            at_5 = review_load_at_error(test, preds, max_error=0.05)
            ci = report.macro_f1_ci
            payload["levels"][level][name] = {
                "macro_f1": report.macro_f1,
                "macro_f1_ci": [ci.low, ci.high] if ci else None,
                "contrast_consistency": report.contrast_consistency,
                "false_mismatch_rate": report.false_mismatch_rate,
                "review_load": report.review_load,
                "review_load_at_5pct_error": at_5.review_load if at_5 else None,
                "per_phenomenon_accuracy": report.per_phenomenon_accuracy,
                "per_language_macro_f1": report.per_language_macro_f1,
            }
            print(
                f"  {name:<14} macro-F1 {report.macro_f1:.4f} "
                f"[{ci.low:.3f}, {ci.high:.3f}]  review {report.review_load:.3f}  "
                f"({time.time() - started:.0f}s)"
            )

        # Paired bootstrap at every level. Two overlapping intervals can still be
        # a significant paired difference -- and two non-overlapping ones do not
        # by themselves license "A beats B" -- so the claim needs its own test.
        # This used to be printed by `kyc-nli compare` and never written down.
        comparisons = {}
        names = list(level_preds)
        for a in range(len(names)):
            for b in range(a + 1, len(names)):
                x, y = names[b], names[a]  # later system minus earlier: ours - baseline
                cmp = paired_bootstrap(
                    test, level_preds[x], level_preds[y], x, y, n_resamples=DEFAULT_RESAMPLES
                )
                comparisons[f"{x}-{y}"] = {
                    "delta": cmp.delta, "ci": [cmp.low, cmp.high],
                    "p_value": cmp.p_value, "significant": cmp.significant,
                }
                print(f"  {cmp}")
        payload["levels"][level]["_paired"] = comparisons

    out = root / "results" / "noise_robustness.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
