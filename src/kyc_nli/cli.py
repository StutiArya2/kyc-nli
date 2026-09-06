"""Command-line entry points.

Every experiment in the paper must be reproducible by one command from this
file plus a config in configs/. If you find yourself running something from a
notebook to produce a number that goes in a table, it belongs here instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from kyc_nli.baselines import BASELINES
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import load_instances, save_instances, split_by_identity, write_manifest
from kyc_nli.evaluation import DEFAULT_RESAMPLES, evaluate, paired_bootstrap
from kyc_nli.languages import load_languages, repo_root
from kyc_nli.schema import Label

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
        Path("data/processed/synth_v0.jsonl"), help="Output JSONL path (gitignored)."
    ),
    identities: int = typer.Option(200, help="Fabricated identities per language."),
    noise: str = typer.Option("moderate", help="clean | light | moderate | heavy"),
    seed: int = typer.Option(20260906, help="Master seed. Recorded in the manifest."),
    split: bool = typer.Option(True, help="Also write train/dev/test splits."),
) -> None:
    """Generate the synthetic benchmark. No real identity data is involved."""
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
    n: int = typer.Option(3, help="Instances to show."),
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
        console.rule(f"{inst.id}  [{inst.language}]  {inst.phenomenon}")
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
    system: str = typer.Argument(..., help=f"One of: {', '.join(BASELINES)}"),
    dataset: Path = typer.Option(Path("data/processed/synth_v0.test.jsonl")),
    out: Path = typer.Option(Path("results/"), help="Where to write the report."),
    bootstrap: int = typer.Option(
        DEFAULT_RESAMPLES, help="Bootstrap resamples for the macro-F1 CI. 0 disables."
    ),
) -> None:
    """Score a non-neural baseline and write a markdown + JSON report."""
    if system not in BASELINES:
        raise typer.BadParameter(f"Unknown system {system!r}. Choose from {list(BASELINES)}.")

    instances = load_instances(_resolve(dataset))
    model = BASELINES[system]()
    predictions = [model.predict(inst) for inst in instances]
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
    for name, cls in BASELINES.items():
        model = cls()
        preds = [model.predict(i) for i in instances]
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


def _resolve(path: Path) -> Path:
    """Interpret relative paths against the repo root, not the shell's cwd."""
    return path if path.is_absolute() else repo_root() / path


if __name__ == "__main__":
    app()
