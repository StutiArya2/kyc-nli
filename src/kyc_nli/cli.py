"""Command-line entry points.

Every experiment in the paper must be reproducible by one command from this
file plus a config in configs/. If you find yourself running something from a
notebook to produce a number that goes in a table, it belongs here instead.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.table import Table

from kyc_nli import demo as demo_module
from kyc_nli.baselines import available_systems
from kyc_nli.data import corpora
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import load_instances, save_instances, split_by_identity, write_manifest
from kyc_nli.evaluation import (
    DEFAULT_RESAMPLES,
    evaluate,
    operating_point_at,
    paired_bootstrap,
    review_load_at_error,
    risk_coverage,
    selective_curve,
)
from kyc_nli.evaluation.transliteration import HEADER, evaluate_transliteration
from kyc_nli.languages import load_languages, repo_root
from kyc_nli.schema import Label
from kyc_nli.translit import get_transliterator

app = typer.Typer(add_completion=False, help="KYC-NLI: document-level NLI for identity fields.")
console = Console()


@app.command()
def languages() -> None:
    """Show the configured language set and why each is in it."""
    table = Table(title="KYC-NLI language set", show_lines=True)
    table.add_column("code")
    table.add_column("script")
    table.add_column("romanisation")
    table.add_column("normative")
    table.add_column("failure mode probed")
    for spec in load_languages().values():
        table.add_row(
            spec.code,
            spec.script.value,
            spec.romanisation.standard,
            spec.romanisation.normative,
            " ".join(spec.failure_mode.split()),
        )
    console.print(table)


@app.command()
def generate(
    out: Path = typer.Option(
        Path("data/processed/synth_v1.jsonl"), help="Output JSONL path (gitignored)."
    ),
    identities: int = typer.Option(200, help="Fabricated identities per language."),
    noise: str = typer.Option("moderate", help="clean | light | moderate | heavy"),
    seed: int = typer.Option(20260906, help="Master seed. Recorded in the manifest."),
    split: bool = typer.Option(True, help="Also write train/dev/test splits."),
) -> None:
    """Generate the synthetic benchmark. No real identity data is involved."""
    out = _resolve(out)
    targets = [out, out.with_suffix(".manifest.json")]
    if split:
        targets += [out.with_name(f"{out.stem}.{name}.jsonl") for name in ("train", "dev", "test")]
    if any(path.exists() for path in targets):
        raise FileExistsError("Refusing to overwrite an existing dataset or manifest")
    if out.name.startswith("synth_v0"):
        raise ValueError("Corrected generation must use a new v1 output path")
    config = GeneratorConfig(
        languages=tuple(load_languages()),
        identities_per_language=identities,
        noise_preset=noise,
        seed=seed,
    )
    generator = InstanceGenerator(config)
    instances = generator.generate()

    out = _resolve(out)
    save_instances(instances, out)
    manifest = write_manifest(
        instances,
        out,
        out.with_suffix(".manifest.json"),
        {
            "languages": list(config.languages),
            "identities_per_language": config.identities_per_language,
            "noise_preset": config.noise_preset,
            "seed": config.seed,
            "alt_romanisation_rate": config.alt_romanisation_rate,
            "dataset_version": config.dataset_version,
        },
    )

    if split:
        for name, subset in split_by_identity(instances).items():
            save_instances(subset, out.with_name(f"{out.stem}.{name}.jsonl"))

    counts = {lab.value: sum(1 for i in instances if i.label is lab) for lab in Label}
    console.print(f"[green]Wrote[/green] {len(instances)} instances to {out}")
    console.print(f"[green]Manifest[/green] {manifest}")
    console.print(f"Label distribution: {counts}")


@app.command()
def inspect(
    dataset: Path = typer.Argument(Path("data/processed/synth_v0.jsonl")),
    # Both spellings: typer derives `--n` from the parameter name, but everyone
    # reaching for a count types `-n`, and three places in our own docs did.
    n: int = typer.Option(3, "-n", "--n", help="Instances to show."),
    language: str = typer.Option("", help="Filter to one language code."),
    phenomenon: str = typer.Option("", help="Filter to one phenomenon."),
) -> None:
    """Print instances in full. Use this before trusting any number."""
    instances = load_instances(_resolve(dataset))
    if language:
        instances = [i for i in instances if i.language == language]
    if phenomenon:
        instances = [i for i in instances if i.phenomenon == phenomenon]

    for inst in instances[:n]:
        # The brackets are escaped: rich reads "[ta]" as a markup tag and the
        # language code -- the one thing you filter on -- disappears from the
        # output entirely.
        console.rule(rf"{inst.id}  \[{inst.language}]  {inst.phenomenon}")
        table = Table(show_header=True)
        table.add_column("zone")
        table.add_column("field")
        table.add_column("observed")
        table.add_column("clean")
        table.add_column("conf", justify="right")
        for obs in inst.premise:
            if obs.field.value == "document_type":
                continue
            table.add_row(
                obs.zone.value,
                obs.field.value,
                obs.value,
                obs.clean_value or "",
                f"{obs.confidence:.2f}",
            )
        console.print(table)
        console.print(f"[bold]Hypothesis:[/bold] {inst.hypothesis.text}")
        console.print(f"[bold]Gold:[/bold] {inst.label.value}")
        console.print(f"[dim]{inst.rationale}[/dim]")


@app.command("run-baseline")
def run_baseline(
    system: str = typer.Argument(..., help="A baseline, or cross_encoder once trained."),
    dataset: Path = typer.Option(Path("data/processed/synth_v0.test.jsonl")),
    out: Path = typer.Option(Path("results/"), help="Where to write the report."),
    bootstrap: int = typer.Option(
        DEFAULT_RESAMPLES, help="Bootstrap resamples for the macro-F1 CI. 0 disables."
    ),
) -> None:
    """Score a non-neural baseline and write a markdown + JSON report."""
    systems = available_systems()
    if system not in systems:
        raise typer.BadParameter(f"Unknown system {system!r}. Available: {list(systems)}.")

    instances = load_instances(_resolve(dataset))
    model = systems[system]()
    predictions = _predict_all(model, instances)
    report = evaluate(system, instances, predictions, bootstrap=bootstrap)

    out_dir = _resolve(out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{system}.md").write_text(report.to_markdown(), encoding="utf-8")
    (out_dir / f"{system}.json").write_text(
        json.dumps(report.__dict__, indent=2, default=str), encoding="utf-8"
    )
    console.print(report.to_markdown())
    console.print(f"\n[green]Report written to[/green] {out_dir / f'{system}.md'}")


@app.command()
def compare(
    dataset: Path = typer.Option(Path("data/processed/synth_v0.test.jsonl")),
    bootstrap: int = typer.Option(
        DEFAULT_RESAMPLES, help="Bootstrap resamples for CIs and the paired test. 0 disables."
    ),
) -> None:
    """Run every baseline on one dataset and print the comparison table.

    This is the go/no-go table. Read the per-phenomenon columns, not the
    headline: if the rule engine is already at ceiling on the phenomena the
    proposal leads with, the framing has to change before any model is trained.

    The paired bootstrap at the end is the test that matters. Two overlapping
    confidence intervals can still be a significant paired difference, so do not
    read significance off the CI column.
    """
    instances = load_instances(_resolve(dataset))
    table = Table(title=f"Baselines on {dataset.name}", show_lines=True)
    for column in (
        "system", "macro-F1", "95% CI", "contrast", "false-mismatch",
        "over-conf(N)", "review load",
    ):
        table.add_column(column)

    predictions: dict[str, list] = {}
    for name, cls in available_systems().items():
        model = cls()
        preds = _predict_all(model, instances)
        predictions[name] = preds
        report = evaluate(name, instances, preds, bootstrap=bootstrap)
        table.add_row(
            name,
            f"{report.macro_f1:.4f}",
            f"[{report.macro_f1_ci.low:.3f}, {report.macro_f1_ci.high:.3f}]"
            if report.macro_f1_ci
            else "--",
            f"{report.contrast_consistency:.4f}",
            f"{report.false_mismatch_rate:.4f}",
            f"{report.overconfident_rate:.4f}",
            f"{report.review_load:.4f}",
        )
    console.print(table)

    if bootstrap:
        names = list(predictions)
        console.print(
            f"\n[bold]Paired bootstrap[/bold] "
            f"({bootstrap} resamples over contrast groups, not instances):"
        )
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                cmp = paired_bootstrap(
                    instances, predictions[a], predictions[b], a, b, n_resamples=bootstrap
                )
                colour = "green" if cmp.significant else "yellow"
                console.print(f"  [{colour}]{cmp}[/{colour}]")


@app.command("risk-coverage")
def risk_coverage_cmd(
    dataset: Path = typer.Option(Path("data/processed/synth_v0.test.jsonl")),
    dev_dataset: Path = typer.Option(
        Path("data/processed/synth_v0.dev.jsonl"),
        help="Where thresholds are CHOSEN. Never the split they are reported on.",
    ),
    out: Path = typer.Option(Path("results/selective-prediction.json")),
    budgets: str = typer.Option(
        "0.10,0.05,0.02,0.01", help="Comma-separated automation error budgets."
    ),
    steps: int = typer.Option(20, help="Points on the plotted curves."),
) -> None:
    """Milestone M4: the selective-prediction view of every available system.

    The headline table reports each system at its own operating point, which is
    not a like-for-like comparison: a system that abstains more buys a lower
    error rate with human labour. This command fixes the error rate instead and
    asks what each system costs to run there, which is the question a compliance
    function actually poses.

    Two answers per budget, because they license different claims:

      oracle     the threshold chosen ON THE TEST SPLIT, by exact search. The
                 best a system could possibly do. Use it only for impossibility:
                 "unreachable even when tuned on the test set".
      dev-tuned  the threshold chosen on DEV, then applied to test. Use it for any
                 claim that a system MEETS a budget. Its test error can exceed
                 the budget; that is the measurement.

    A system that cannot reach a budget is reported as such, never as "100%
    review" -- declining to answer is not meeting a target.
    """
    instances = load_instances(_resolve(dataset))
    dev_path = _resolve(dev_dataset)
    dev = load_instances(dev_path) if dev_path.exists() else None
    if dev is None:
        console.print(f"[yellow]No dev split at {dev_path}; reporting oracle points only.[/yellow]")
    targets = [float(b) for b in budgets.split(",") if b.strip()]

    table = Table(title=f"Review load at a fixed automation error ({dataset.name})")
    table.add_column("system")
    table.add_column("own point", justify="right")
    for b in targets:
        table.add_column(f"err <= {b:.0%}", justify="right")

    payload: dict[str, dict] = {}
    for name, cls in available_systems().items():
        model = cls()
        preds = _predict_all(model, instances)
        dev_preds = _predict_all(model, dev) if dev is not None else None
        curve = selective_curve(instances, preds, steps=steps)
        own = curve[0]
        row = [name, f"{own.review_load:.1%} @ {own.error_on_auto:.1%}"]
        oracle_rows, tuned_rows = {}, {}
        for b in targets:
            oracle = review_load_at_error(instances, preds, max_error=b)
            oracle_rows[f"{b}"] = oracle.as_row() if oracle else None
            tuned = None
            if dev is not None and dev_preds is not None:
                chosen = review_load_at_error(dev, dev_preds, max_error=b)
                if chosen is not None:
                    applied = operating_point_at(instances, preds, chosen.threshold)
                    tuned = {"dev": chosen.as_row(), "test": applied.as_row()}
            tuned_rows[f"{b}"] = tuned
            # The table shows the claim-bearing number: dev-tuned where a dev
            # split exists, with the error it actually achieved on test.
            if dev is not None:
                if tuned is None:
                    cell = "unreachable"
                else:
                    t = tuned["test"]
                    cell = f"{t['review_load']:.1%} ({t['error_on_auto']:.1%})"
            else:
                cell = "unreachable" if oracle is None else f"{oracle.review_load:.1%}"
            row.append(cell)
        table.add_row(*row)
        payload[name] = {
            "own_operating_point": own.as_row(),
            "review_load_at_error": oracle_rows,
            "dev_tuned": tuned_rows,
            "selective_curve": [p.as_row() for p in curve],
            "risk_coverage": [
                {"coverage": c, "risk": r} for c, r in risk_coverage(instances, preds, steps=steps)
            ],
        }

    console.print(table)
    if dev is not None:
        console.print(
            "[dim]Cells: test review load (test error) with the threshold chosen on dev.[/dim]"
        )
    out_path = _resolve(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    console.print(f"\n[green]Curves written to[/green] {out_path}")


@app.command()
def serve(
    port: int = typer.Option(8765, help="Port on localhost."),
    host: str = typer.Option(
        "127.0.0.1", help="Interface to bind. Keep the default unless you mean to expose it."
    ),
    browser: bool = typer.Option(True, help="Open the interface in a browser."),
) -> None:
    """Open the interactive explorer in a browser.

    Browse the benchmark, step one document from clean to heavy OCR noise, edit
    a claim, and watch all three systems decide live. Uses the noise-robustness
    splits (`python scripts/noise_robustness.py`) and the trained cross-encoder
    when present, and degrades to whatever exists when they are not.
    """
    from kyc_nli.app.server import serve as run

    run(host=host, port=port, open_browser=browser)


@app.command("fetch-dakshina")
def fetch_dakshina(
    force: bool = typer.Option(False, help="Re-download even if already present."),
) -> None:
    """Download the Dakshina dataset into data/external/ (gitignored, ~2 GB).

    Never called automatically: no test run and no `generate` should silently
    pull 2 GB off the network.
    """
    if corpora.is_available() and not force:
        console.print("[green]Already present[/green] at data/external/")
    else:
        console.print("Downloading Dakshina (~2 GB, CC BY-SA 4.0)...")
        path = corpora.download(force=force)
        console.print(f"[green]Extracted to[/green] {path}")

    table = Table(title="Dakshina romanisation lexicons", show_lines=True)
    for c in ("lang", "native words", "attested spellings", "words with >1 spelling", "files"):
        table.add_column(c)
    for lang, stats in corpora.corpus_summary().items():
        table.add_row(
            lang,
            f"{stats['entries']:,}",
            f"{stats.get('spellings', 0):,}",
            f"{stats.get('multi_spelling_entries', 0):,}",
            str(stats["files"]),
        )
    console.print(table)


@app.command("translit-eval")
def translit_eval(
    sample: int = typer.Option(2000, help="Native words sampled per language. 0 = all."),
    seed: int = typer.Option(20260906, help="Sampling seed."),
    out: Path = typer.Option(Path("results/transliteration.md"), help="Report path."),
) -> None:
    """Score the transliteration engines against real human romanisations.

    Replaces the hand-written 40-pair recall figures with a measurement over
    thousands of romanisations written by native speakers. Also measures how
    one-to-many romanisation actually is -- the premise the project rests on,
    which until now was asserted from three hand-picked examples.
    """
    if not corpora.is_available():
        raise typer.BadParameter(
            "Dakshina is not present. Run `kyc-nli fetch-dakshina` first."
        )

    lines = [
        "# Transliteration engines vs. human romanisations (Dakshina)",
        "",
        f"Sample: {sample or 'all'} native words per language, seed {seed}.",
        "Dakshina v1.0, CC BY-SA 4.0. Romanisations are human-elicited.",
        "",
        "Scored on the **test** split. The lexicon condition attaches attested",
        "spellings from the **train** split only -- a lexicon built from the",
        "scored split would measure memorisation, not transliteration.",
        "",
        "## Rules only",
        "",
        HEADER,
    ]
    table = Table(title="Engines vs. human romanisations (test split)", show_lines=True)
    for c in ("lang", "words", "any-recall", "top1-recall", "spelling-recall",
              "mean variants", "spellings/word"):
        table.add_column(c)

    lex_lines: list[str] = ["", "## Rules + train-split lexicon", "", HEADER]
    for language in corpora.DAKSHINA_LANGUAGES:
        entries = corpora.load_romanisations(language, split="test")
        if not entries:
            console.print(f"[yellow]No test lexicon for {language}; skipping.[/yellow]")
            continue

        spec = load_languages()[language]
        engine = get_transliterator(spec.script, language)
        engine.attach_lexicon({})
        rules = evaluate_transliteration(language, entries, sample=sample or None, seed=seed)

        engine.attach_lexicon(corpora.build_lexicon(language, split="train"))
        withlex = evaluate_transliteration(language, entries, sample=sample or None, seed=seed)
        engine.attach_lexicon({})

        lines.append(rules.to_row())
        lex_lines.append(withlex.to_row())
        table.add_row(
            language,
            f"{rules.n_words:,}",
            f"{rules.any_recall:.3f} -> {withlex.any_recall:.3f}",
            f"{rules.top1_recall:.3f} -> {withlex.top1_recall:.3f}",
            f"{rules.spelling_recall:.3f} -> {withlex.spelling_recall:.3f}",
            f"{rules.mean_variants:.0f} -> {withlex.mean_variants:.0f}",
            f"{rules.mean_spellings_per_word:.2f}",
        )

    lines += lex_lines
    console.print(table)
    console.print("[dim]rules only -> rules + train-split lexicon[/dim]")
    out_path = _resolve(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    console.print(f"[green]Report written to[/green] {out_path}")


@app.command("calibrate-ocr")
def calibrate_ocr(
    words: int = typer.Option(60, help="Words per language per degradation level."),
    fetch: bool = typer.Option(False, help="Download the pinned Noto fonts first."),
    out: Path = typer.Option(Path("results/ocr-calibration.md"), help="Report path."),
    seed: int = typer.Option(20260906),
    write_tables: bool = typer.Option(
        False, help="Overwrite src/kyc_nli/ocr/measured.py with the measured tables."
    ),
) -> None:
    """Measure what a real OCR engine does to each script (milestone M1).

    Renders known text with correct complex-script shaping, degrades it to
    approximate capture conditions, OCRs it, and aligns the result against the
    input. Produces per-script character error rates and confusion tables to
    replace the hand-built ones in kyc_nli.ocr.noise.

    NOT calibrated on MIDV-2020: that corpus contains no Devanagari, Tamil,
    Bengali or Perso-Arabic document, so it cannot calibrate four of our five
    languages. See docs/decisions/0006-ocr-calibration.md.
    """
    try:
        from kyc_nli.ocr import calibrate as ocr_calibrate
        from kyc_nli.ocr import render as ocr_render
    except ImportError as err:
        raise typer.BadParameter(
            "OCR calibration requires optional OCR dependencies (pillow, uharfbuzz, freetype-py). "
            "Install with: pip install -e \".[ocr]\""
        ) from err

    if fetch or not ocr_render.fonts_available():
        console.print("Fetching pinned Noto fonts...")
        console.print(f"[green]Fonts at[/green] {ocr_render.download_fonts()}")
    if fetch or not ocr_calibrate.tessdata_dir().is_dir():
        console.print("Fetching Tesseract language packs (no admin rights needed)...")
        console.print(f"[green]Language packs at[/green] {ocr_calibrate.download_langs()}")

    missing = [
        lang for lang in ocr_calibrate.TESSERACT_LANGS
        if not ocr_calibrate.is_available((lang,))
    ]
    if missing:
        have = sorted(ocr_calibrate.available_langs()) or ["<tesseract not found>"]
        raise typer.BadParameter(
            f"Tesseract cannot handle {missing}. Installed: {have}. "
            f"Install Tesseract and the hin/tam/ben/urd/eng language packs; "
            f"see docs/plan.md M1."
        )

    lines = [
        "# OCR calibration (milestone M1)",
        "",
        f"Rendered with pinned Noto fonts, shaped via HarfBuzz. {words} words per",
        f"language per level, seed {seed}. Tesseract {ocr_calibrate.tesseract_path()}.",
        "",
        "Rendered text has no paper grain, print texture, glare or perspective.",
        "Degradation levels approximate capture conditions; they are not measured",
        "from a device. See docs/decisions/0006-ocr-calibration.md.",
        "",
        "| lang | level | words | chars | CER | sub | del | ins | blank |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    table = Table(title="Measured OCR character error rate", show_lines=True)
    table.add_column("lang")
    for level in ocr_render.DEGRADE_LEVELS:
        table.add_column(level.name.replace("_", " "))

    confusion_sections: list[str] = ["", "## Measured confusions", ""]
    results: dict[str, ocr_calibrate.CalibrationResult] = {}
    for language in ocr_calibrate.TESSERACT_LANGS:
        sample = _calibration_words(language, words, seed)
        console.print(f"  calibrating [bold]{language}[/bold] on {len(sample)} words...")
        result = ocr_calibrate.calibrate_language(language, sample, seed=seed)
        results[language] = result
        for lr in result.levels:
            lines.append(
                f"| {language} | {lr.level} | {lr.n_words} | {lr.n_chars} | "
                f"{lr.cer:.3f} | {lr.substitution_rate:.3f} | {lr.deletion_rate:.3f} | "
                f"{lr.insertion_rate:.3f} | {lr.blank_rate:.3f} |"
            )
        table.add_row(language, *[f"{lr.cer:.3f}" for lr in result.levels])
        pairs = result.confusion_table(min_count=2)
        confusion_sections.append(f"### {language}")
        confusion_sections.append("")
        body = "\n".join(f"    {k!r}: {v!r}," for k, v in list(pairs.items())[:40])
        confusion_sections.append(f"```python\n{body}\n```")
        confusion_sections.append("")

    console.print(table)
    out_path = _resolve(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines + confusion_sections) + "\n", encoding="utf-8")
    console.print(f"[green]Report written to[/green] {out_path}")

    if write_tables:
        module = _resolve(Path("src/kyc_nli/ocr/measured.py"))
        module.write_text(
            ocr_calibrate.render_measured_module(results, words, seed), encoding="utf-8"
        )
        console.print(f"[green]Measured tables written to[/green] {module}")
        console.print(
            "[yellow]Now re-run:[/yellow] kyc-nli generate && kyc-nli compare"
        )


@app.command()
def demo(
    dataset: Path = typer.Option(
        None, help="Benchmark to score. Defaults to the test split, generating one if absent."
    ),
    bootstrap: int = typer.Option(300, help="Resamples for the live CIs. 0 is faster."),
    step: int = typer.Option(0, help="Show only section 1-5. 0 shows all."),
    sample: int = typer.Option(
        demo_module.DEMO_SAMPLE,
        help="Instances to score. 0 uses the full split (minutes on CPU).",
    ),
) -> None:
    """Run the presentation walkthrough. One command, about a minute.

    Built for showing live: no network, no GPU, and it degrades gracefully if the
    neural model or the Dakshina corpus is missing rather than failing in front
    of an audience. Every number on screen is computed at the moment it appears.
    """
    demo_module.run(
        dataset=str(dataset) if dataset else None,
        bootstrap=bootstrap,
        only=step,
        sample=sample,
    )


@app.command("freeze-v1")
def freeze_v1(
    config: Path = typer.Option(Path("configs/experiments/v1_freeze.yaml")),
) -> None:
    """Freeze corrected negatives with unchanged identity/OCR streams and split IDs."""
    from kyc_nli.v1 import freeze

    console.print(f"Frozen manifest: {freeze(config)}")


@app.command("evaluate-v1")
def evaluate_frozen_v1(
    config: Path = typer.Option(Path("configs/experiments/v1_evaluate.yaml")),
) -> None:
    """Evaluate independently hashed checkpoints and baselines on frozen v1."""
    from kyc_nli.v1 import evaluate_v1

    console.print(f"Evaluation: {evaluate_v1(config)}")


@app.command("selective-v1")
def selective_frozen_v1(
    config: Path = typer.Option(Path("configs/experiments/v1_selective.yaml")),
) -> None:
    """Lock v1 selective thresholds on dev, then score the preserved test predictions."""
    from kyc_nli.selective_v1 import run

    console.print(f"Selective evaluation: {run(config)}")


@app.command("annotation-v1")
def annotation_v1(
    config: Path = typer.Option(Path("configs/experiments/v1_annotation.yaml")),
) -> None:
    """Prepare blank blinded v1 worksheets and a separately stored analyst key."""
    from kyc_nli.annotation_v1 import prepare

    console.print(f"Annotation batch: {prepare(config)}")


@app.command("check-annotation-v1")
def check_annotation_v1(
    batch: Path = typer.Option(...), sheet_a: Path = typer.Option(...),
    sheet_b: Path = typer.Option(...),
) -> None:
    """Validate returned worksheets; never infer independence from labels alone."""
    from kyc_nli.annotation_v1 import check

    console.print(f"Annotation check: {check(batch, sheet_a, sheet_b)}")


@app.command("paper-v1")
def paper_v1(
    config: Path = typer.Option(Path("configs/experiments/paper_v1.yaml")),
) -> None:
    """Generate manuscript tables, figures and prose numbers from pinned v1 results."""
    from kyc_nli.paper_v1 import run

    console.print(f"Paper build: {run(config)}")


@app.command("pilot-report-v1")
def pilot_report_v1(
    config: Path = typer.Option(Path("configs/experiments/v1_pilot_report.yaml")),
) -> None:
    """Preserve human submissions and report candidate labels, uncertainty and limitations."""
    from kyc_nli.pilot_report import run

    console.print(f"Pilot report: {run(config)}")


@app.command("trace-v0")
def trace_v0(
    config: Path = typer.Option(
        Path("configs/experiments/v0_trace.yaml"), help="Frozen v0 trace configuration."
    ),
) -> None:
    """Run preserved XLM-R weights at length 192 and audit historical predictions."""
    from kyc_nli.nli.trace import run_trace

    output = run_trace(config)
    console.print(f"Trace saved to {output}")


@app.command("investigate-v0")
def investigate_v0(
    config: Path = typer.Option(
        Path("configs/experiments/v0_trace_investigation.yaml"),
        help="Archive comparison configuration; requires a completed primary trace.",
    ),
) -> None:
    """Check archived weights on the same wrong-name subset, without retraining."""
    import runpy

    namespace = runpy.run_path(str(repo_root() / "scripts/investigate_v0_trace.py"))
    output = namespace["run"](config)
    console.print(f"Investigation saved to {output}")


def _calibration_words(language: str, n: int, seed: int) -> list[str]:
    """Real words where we have them, falling back to the embedded name pool."""
    import random

    from kyc_nli.data.name_pools import pool_for

    if language != "en" and corpora.is_available():
        entries = corpora.load_romanisations(language, split="test")
        if entries:
            picks = random.Random(seed).sample(entries, min(n, len(entries)))
            return [e.native for e in picks]
    pool = pool_for(language)
    candidates = [native for native, _ in pool.surnames + pool.given]
    return candidates[:n]


def _predict_all(model, instances: list) -> list:
    """Score every instance, batching when the system supports it.

    A transformer is an order of magnitude faster batched, and the harness scores
    instance-by-instance. Same predictions, same order -- a performance detail,
    not a different computation.
    """
    batched = getattr(model, "predict_all", None)
    if callable(batched):
        return batched(instances)
    return [model.predict(i) for i in instances]


def _resolve(path: Path) -> Path:
    """Interpret relative paths against the repo root, not the shell's cwd."""
    return path if path.is_absolute() else repo_root() / path


if __name__ == "__main__":
    app()
