"""Render every figure in the paper from machine-written results.

    pip install -e ".[paper]"
    python scripts/make_figures.py            # all figures -> paper/figures/
    python scripts/make_figures.py selective  # just one, while iterating

Nothing in here computes a result. Each figure reads a file that a pipeline
command wrote, so a figure can never disagree with the table beside it:

    fig1_task           data/processed/synth_v0.test.jsonl + the three systems
    fig2_motivation     Dakshina (kyc_nli.data.corpora) + kyc_nli.ocr.measured
    fig3_noise          results/noise_robustness.json   scripts/noise_robustness.py
    fig4_selective      results/selective-prediction.json   kyc-nli risk-coverage
    fig5_phenomena      results/noise_robustness.json   scripts/noise_robustness.py

Design choices, each answering a reviewer or a printer:

* Every figure is written as PDF with TrueType fonts (pdf.fonttype 42). ACL's
  submission checker rejects Type 3 fonts, which is matplotlib's default.
* Each system keeps ONE colour and ONE marker across every figure. The marker
  is what survives a greyscale print; colour alone would not.
* The palette is the dataviz reference instance, validated for colour-vision
  deficiency rather than eyeballed. The aqua slot sits below 3:1 contrast on
  white, which is why every series is also identified by legend or label.
* Indic text is shaped by the project's own HarfBuzz renderer and embedded as an
  image. matplotlib does no complex-script shaping, so typing Devanagari into a
  text artist would place the vowel signs and the reph wrongly -- the exact bug
  the OCR calibration had to work around in Pillow.
"""

from __future__ import annotations

import json
import sys

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.offsetbox import AnnotationBbox, OffsetImage  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from kyc_nli.languages import load_languages, repo_root  # noqa: E402

ROOT = repo_root()
RESULTS = ROOT / "results"
OUT = ROOT / "paper" / "figures"

# --------------------------------------------------------------------------
# Design tokens
# --------------------------------------------------------------------------

#: Draw order. Ours last, so its line sits on top where curves cross.
SYSTEMS = ("exact_match", "rule_engine", "cross_encoder")
COLOR = {"cross_encoder": "#2a78d6", "rule_engine": "#eb6834", "exact_match": "#1baf7a"}
MARKER = {"cross_encoder": "o", "rule_engine": "s", "exact_match": "^"}
LABEL = {
    "cross_encoder": "Cross-encoder (ours)",
    "rule_engine": "Rule engine",
    "exact_match": "Exact match",
}

INK, INK2, MUTED = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"
#: "Measured from real data" in the motivation figure. Deliberately not a
#: system colour: a reader who learned "blue is the model" must not see blue
#: on a chart that has no model in it.
MEASURED = "#6250d6"
#: The retired hand-built noise model: grey, because it is the thing being
#: corrected, not a peer of the measurement.
RETIRED = "#a9a79e"
#: Status colours. Only where the colour genuinely means right/wrong, and always
#: beside an icon and a word.
GOOD, BAD = "#0ca30c", "#d03b3b"

COL_W = 3.03  # ACL single-column width, inches (219pt)
FULL_W = 6.30  # ACL two-column text width, inches (455pt)


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.titlesize": 8.5,
            "axes.titleweight": "bold",
            "axes.titlelocation": "left",
            "axes.labelsize": 8,
            "xtick.labelsize": 7.5,
            "ytick.labelsize": 7.5,
            "legend.fontsize": 7.5,
            "axes.edgecolor": AXIS,
            "axes.linewidth": 0.8,
            "axes.labelcolor": INK2,
            "xtick.color": AXIS,
            "ytick.color": AXIS,
            "xtick.labelcolor": INK2,
            "ytick.labelcolor": INK2,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "grid.linestyle": "-",  # solid hairline: a dashed grid reads as a threshold
            "axes.axisbelow": True,
            "legend.frameon": False,
            "legend.handlelength": 1.6,
            "pdf.fonttype": 42,  # TrueType. ACL rejects Type 3 fonts.
            "ps.fonttype": 42,
            "savefig.dpi": 300,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "text.color": INK,
        }
    )


def save(fig, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote paper/figures/{name}.pdf (+ .png)")


def _load(name: str, produced_by: str) -> dict | None:
    path = RESULTS / name
    if not path.exists():
        print(f"  SKIP: {path.name} missing -- produce it with `{produced_by}`")
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _system_legend(ax, systems, **kw) -> None:
    handles = [
        plt.Line2D(
            [], [], color=COLOR[s], marker=MARKER[s], lw=1.6, ms=4.5,
            mec="white", mew=0.6, label=LABEL[s],
        )
        for s in systems
    ]
    ax.legend(handles=handles, **kw)


# --------------------------------------------------------------------------
# Figure 1 -- the task, on a real instance
# --------------------------------------------------------------------------


def _shaped(text: str, script, height_pt: float):
    """Indic text as a correctly shaped image artist, ``height_pt`` tall."""
    from kyc_nli.ocr import render

    img = np.asarray(render.render(text, script, size_px=160, padding=24), dtype=float)
    ink = img < 250
    rows, cols = np.where(ink)
    img = img[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]
    # White -> transparent, black -> ink, so the glyphs sit on any fill.
    alpha = 1.0 - img / 255.0
    rgba = np.zeros((*img.shape, 4))
    rgba[..., :3] = matplotlib.colors.to_rgb(INK)
    rgba[..., 3] = alpha
    return OffsetImage(rgba, zoom=height_pt / img.shape[0], interpolation="lanczos")


def fig1_task() -> None:
    """The first Hindi test identity, through all three systems.

    Not selected for the outcome: hi-00000 is simply the first Hindi identity in
    the held-out split, and it was chosen as the running example in
    docs/HOW-IT-WORKS.md before these predictions were looked at.
    """
    from kyc_nli.baselines import available_systems
    from kyc_nli.data.io import load_instances
    from kyc_nli.schema import Field, Script, Zone

    test = load_instances(ROOT / "data" / "processed" / "synth_v0.test.jsonl")
    inst = next(i for i in test if i.id == "hi-00000-name-e")
    viz = inst.observation(Field.SURNAME, Zone.VIZ)
    mrz = inst.observation(Field.SURNAME, Zone.MRZ)
    systems = available_systems()
    preds = {name: systems[name]().predict(inst) for name in SYSTEMS if name in systems}

    # Layout is in axis units: 100 across 6.3in, so 1 unit ~ 4.5pt. Text widths
    # were measured against that, not guessed -- the first draft overprinted in
    # four places.
    fig, ax = plt.subplots(figsize=(FULL_W, 2.05))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 33)
    ax.axis("off")

    def box(x0, x1, y0, y1, title, fill="#f7f7f5"):
        ax.add_patch(
            FancyBboxPatch(
                (x0, y0), x1 - x0, y1 - y0,
                boxstyle="round,pad=0,rounding_size=1.2", fc=fill, ec=AXIS, lw=0.8,
            )
        )
        if title:
            ax.text(x0 + 1.5, y1 - 1.6, title, fontsize=7.3, fontweight="bold", color=INK2,
                    va="top")

    def arrow(x0, x1, y, label=None):
        ax.add_patch(
            FancyArrowPatch(
                (x0, y), (x1, y), arrowstyle="-|>", mutation_scale=7.5,
                color=INK2, lw=0.9, shrinkA=0, shrinkB=0,
            )
        )
        if label:
            ax.text((x0 + x1) / 2, y + 1.1, label, fontsize=6.1, color=INK2, ha="center",
                    va="bottom", linespacing=1.1)

    def zone(x, y, name):
        ax.text(x, y, name, fontsize=6.2, color=MUTED, va="center", fontweight="bold")

    def shaped(text, x, y):
        ax.add_artist(AnnotationBbox(_shaped(text, Script.DEVANAGARI, 10.5), (x, y),
                                     frameon=False, box_alignment=(0, 0.5)))

    mono = {"family": "DejaVu Sans Mono", "fontsize": 7.7, "va": "center", "color": INK}
    conf = {"fontsize": 6.0, "color": MUTED, "va": "center"}
    VIZ_Y, MRZ_Y = 23.2, 14.6

    # Column 1: what was printed.
    box(0.5, 19.5, 9, 31, "Printed document")
    zone(2.2, VIZ_Y, "VIZ")
    shaped(viz.clean_value, 7.4, VIZ_Y)
    zone(2.2, MRZ_Y, "MRZ")
    ax.text(7.4, MRZ_Y, mrz.clean_value, **mono)

    arrow(20.0, 26.0, 20.0, "OCR\nmeasured")

    # Column 2: what the systems actually receive. Confidence sits under each
    # value rather than beside it, which is where it collided with the text.
    box(26.5, 50.5, 9, 31, "As read by OCR")
    zone(28.2, VIZ_Y, "VIZ")
    shaped(viz.value, 33.4, VIZ_Y)
    ax.text(33.4, VIZ_Y - 3.6, f"confidence {viz.confidence:.2f}", **conf)
    zone(28.2, MRZ_Y, "MRZ")
    ax.text(33.4, MRZ_Y, mrz.value, **mono)
    ax.text(33.4, MRZ_Y - 3.4, f"confidence {mrz.confidence:.2f}", **conf)

    # The claim runs under both document columns: it is checked against the
    # document, not against either zone on its own.
    box(0.5, 50.5, 0.5, 6.6, None, fill="white")
    ax.text(2.2, 3.55, "Claim:", fontsize=6.7, color=MUTED, fontweight="bold", va="center")
    ax.text(9.9, 3.55, inst.hypothesis.text, fontsize=6.7, color=INK, va="center")

    arrow(51.0, 57.0, 20.0, "premise")
    arrow(51.0, 57.0, 3.55, "claim")

    # Column 3: three systems, one input.
    box(57.5, 99.5, 0.5, 31, "Three systems")
    # The gold label sits on the title line, right-aligned: beside the claim it
    # overprinted the hypothesis text.
    ax.text(98.3, 29.4, f"gold: {inst.label.value.upper()}", fontsize=6.4, color=INK2,
            fontweight="bold", va="top", ha="right")
    outcome = {
        "exact_match": ("rejects a real customer", False),
        "rule_engine": ("sent to a human reviewer", None),
        "cross_encoder": ("correct, automated", True),
    }
    for row, name in enumerate(s for s in SYSTEMS if s in preds):
        y = 22.8 - row * 8.3
        p = preds[name]
        ax.plot(59.7, y, marker=MARKER[name], color=COLOR[name], ms=5.0, mec="white", mew=0.6,
                clip_on=False)
        ax.text(61.4, y, LABEL[name].replace(" (ours)", ""), fontsize=6.9, color=INK,
                va="center")
        verdict = p.label.value.upper()
        if name == "cross_encoder":
            verdict += f"  {p.confidence:.2f}"
        ax.text(76.6, y + 1.25, verdict, fontsize=6.9, fontweight="bold", color=INK,
                va="center")
        note, good = outcome[name]
        icon = {True: "✓ ", False: "✗ ", None: ""}[good]
        colour = {True: GOOD, False: BAD, None: INK2}[good]
        ax.text(76.6, y - 1.6, icon + note, fontsize=6.1, color=colour, va="center")

    save(fig, "fig1_task")


# --------------------------------------------------------------------------
# Figure 2 -- the two premises, measured
# --------------------------------------------------------------------------

#: The retired hand-built noise model's (substitution, deletion) rates, kept here
#: only so the figure can show what the measurement corrected. They are the old
#: preset values, recorded in docs/m1-ocr-calibration-findings.md, Finding 1 --
#: configuration, not a measurement, and never used to produce a result.
HAND_BUILT = {"light": (0.030, 0.005), "moderate": (0.080, 0.010), "heavy": (0.180, 0.040)}
#: Which measured capture condition each benchmark preset was calibrated from.
PRESET_SOURCE = {"light": "phone_photo", "moderate": "poor_capture", "heavy": "severe"}


def fig2_motivation() -> None:
    from kyc_nli.data import corpora
    from kyc_nli.ocr.measured import MEASURED_RATES

    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL_W, 2.2), gridspec_kw={"wspace": 0.34})

    # (a) Romanisation is one-to-many, by language.
    if corpora.is_available():
        names = {c: s.name for c, s in load_languages().items()}
        summary = corpora.corpus_summary()
        langs = [c for c in corpora.DAKSHINA_LANGUAGES if c in summary]
        share = [100 * summary[c]["multi_spelling_entries"] / summary[c]["entries"] for c in langs]
        per_word = [summary[c]["spellings"] / summary[c]["entries"] for c in langs]
        x = np.arange(len(langs))
        a.bar(x, share, width=0.58, color=MEASURED, edgecolor="white", linewidth=1)
        for xi, v in zip(x, share, strict=True):
            a.text(xi, v + 2, f"{v:.0f}%", ha="center", va="bottom", fontsize=7.5, color=INK)
        a.set_xticks(x, [f"{names[c]}\n{w:.1f} / word" for c, w in zip(langs, per_word,
                                                                       strict=True)])
        a.tick_params(axis="x", labelsize=6.8)  # four two-line labels must fit
        a.set_ylim(0, 110)
        a.set_yticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
        a.set_ylabel("Words with >1 human romanisation")
        a.grid(axis="x", visible=False)
        a.set_title("(a)  One word, many correct spellings")
    else:
        a.text(0.5, 0.5, "Dakshina not downloaded\n(kyc-nli fetch-dakshina)",
               transform=a.transAxes, ha="center", va="center", color=MUTED)
        a.axis("off")

    # (b) Deletion vs substitution: the hand-built model had the shape backwards.
    levels = list(PRESET_SOURCE)
    rates = [MEASURED_RATES[PRESET_SOURCE[lv]] for lv in levels]
    measured = [r["deletion"] / r["substitution"] for r in rates]
    guessed = [HAND_BUILT[lv][1] / HAND_BUILT[lv][0] for lv in levels]
    x = np.arange(len(levels))
    off = 0.13
    b.axhline(1.0, color=INK2, lw=0.8)
    # In the empty gap between the first two groups: anywhere else it sits on a stem.
    b.text(0.5, 1.07, "deletion =\nsubstitution", fontsize=6.3, color=INK2,
           ha="center", va="bottom", linespacing=1.05)
    for series, xs, colour, label in (
        (guessed, x - off, RETIRED, "Hand-built (retired)"),
        (measured, x + off, MEASURED, "Measured (Tesseract)"),
    ):
        b.vlines(xs, 1.0, series, color=colour, lw=1.6)
        b.plot(xs, series, "o", color=colour, ms=5, mec="white", mew=0.7, label=label)
        for xi, v in zip(xs, series, strict=True):
            above = v > 1
            b.text(xi, v * (1.18 if above else 1 / 1.18), f"{v:.1f}×" if v >= 1 else f"{v:.2f}×",
                   ha="center", va="bottom" if above else "top", fontsize=6.6, color=INK)
    b.set_yscale("log")
    b.set_ylim(0.07, 7)
    b.set_yticks([0.1, 0.25, 0.5, 1, 2, 4], ["0.1×", "0.25×", "0.5×", "1×",
                                              "2×", "4×"])
    b.minorticks_off()
    b.set_xticks(x, [lv.capitalize() for lv in levels])
    b.set_xlim(-0.55, len(levels) - 0.45)
    b.set_ylabel("Deletion rate ÷ substitution rate")
    b.grid(axis="x", visible=False)
    b.legend(loc="upper right", handletextpad=0.4)  # the lower half carries value labels
    b.set_title("(b)  OCR deletes more than it substitutes")

    save(fig, "fig2_motivation")


# --------------------------------------------------------------------------
# Figure 3 -- robustness to capture quality
# --------------------------------------------------------------------------

LEVELS = ("clean", "light", "moderate", "heavy")


def fig3_noise() -> None:
    data = _load("noise_robustness.json", "python scripts/noise_robustness.py")
    if data is None:
        return
    systems = [s for s in SYSTEMS if s in data["levels"]["moderate"]]
    x = np.arange(len(LEVELS))

    fig, ax = plt.subplots(figsize=(COL_W, 2.3))
    for s in systems:
        rows = [data["levels"][lv][s] for lv in LEVELS]
        y = [r["macro_f1"] for r in rows]
        lo = [r["macro_f1_ci"][0] for r in rows]
        hi = [r["macro_f1_ci"][1] for r in rows]
        ax.fill_between(x, lo, hi, color=COLOR[s], alpha=0.16, lw=0)
        ax.plot(x, y, color=COLOR[s], lw=1.6, marker=MARKER[s], ms=4.5, mec="white", mew=0.7,
                zorder=3)

    trained = LEVELS.index(data.get("trained_at", "moderate"))
    ax.axvline(trained, color=AXIS, lw=0.8, zorder=1)
    ax.text(trained + 0.06, 0.04, "model trained\nat this level", fontsize=6.3, color=INK2,
            va="bottom", linespacing=1.1)

    ax.set_xticks(x, [lv.capitalize() for lv in LEVELS])
    ax.set_xlim(-0.2, len(LEVELS) - 0.8)
    ax.set_ylim(0, 1.04)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_ylabel("Macro-F1 (95% CI)")
    ax.set_xlabel("OCR noise level")
    ax.grid(axis="x", visible=False)
    _system_legend(ax, systems, loc="center left", bbox_to_anchor=(0.0, 0.64), handletextpad=0.5)
    save(fig, "fig3_noise")


# --------------------------------------------------------------------------
# Figure 4 -- the selective-prediction result
# --------------------------------------------------------------------------


def _dedupe(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    out: list[tuple[float, float]] = []
    for p in points:
        if not out or (abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9):
            out.append(p)
    return out


def fig4_selective() -> None:
    data = _load("selective-prediction.json", "kyc-nli risk-coverage --steps 50")
    if data is None:
        return
    systems = [s for s in SYSTEMS if s in data]

    fig, (a, b) = plt.subplots(1, 2, figsize=(FULL_W, 2.45), gridspec_kw={"wspace": 0.3})

    # (a) Review load against automation error. Lower-left is better.
    budget = 5.0
    a.axhspan(0, budget, color=COLOR["cross_encoder"], alpha=0.05, lw=0)
    a.axhline(budget, color=INK2, lw=0.8, ls=(0, (3, 2)))  # a real threshold, so dashed
    a.text(60, budget + 0.35, "5% error budget", fontsize=6.5, color=INK2, ha="right", va="bottom")

    for s in systems:
        own = data[s]["own_operating_point"]
        if s == "exact_match":
            # 0% review at 54% error: off this axis by a factor of four. Shown as
            # an arrow at the top edge rather than by stretching the axis until
            # the two systems that matter are flat lines.
            ex = own["review_load"] * 100 + 1.2
            a.annotate(
                "", xy=(ex, 17.4), xytext=(ex, 15.1),
                arrowprops={"arrowstyle": "-|>", "color": COLOR[s], "lw": 1.2, "mutation_scale": 7},
            )
            a.plot(own["review_load"] * 100 + 1.2, 14.8, marker=MARKER[s], color=COLOR[s], ms=5,
                   mec="white", mew=0.6, clip_on=False)
            a.text(3.6, 16.1, f"Exact match: {own['error_on_auto'] * 100:.0f}% error,\n"
                              f"off scale", fontsize=6.4, color=INK2, va="center")
            continue
        pts = _dedupe([
            (p["review_load"] * 100, p["error_on_auto"] * 100)
            for p in data[s]["selective_curve"] if p["n_auto"] > 0
        ])
        xs, ys = zip(*pts, strict=True)
        a.plot(xs, ys, color=COLOR[s], lw=1.6, marker=MARKER[s], ms=3.2, mec="white", mew=0.5,
               zorder=3)
        ox, oy = own["review_load"] * 100, own["error_on_auto"] * 100
        a.plot(ox, oy, marker=MARKER[s], color=COLOR[s], ms=7, mec="white", mew=1.0, zorder=4)

    ce, re_ = data.get("cross_encoder"), data.get("rule_engine")
    if ce:
        o = ce["own_operating_point"]
        a.annotate(f"{o['review_load'] * 100:.1f}% review\n{o['error_on_auto'] * 100:.1f}% error",
                   xy=(o["review_load"] * 100, o["error_on_auto"] * 100),
                   xytext=(o["review_load"] * 100 + 6, 8.6), fontsize=6.4, color=INK2,
                   arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 0.7})
    if re_:
        o = re_["own_operating_point"]
        a.annotate(f"{o['review_load'] * 100:.1f}% review\n{o['error_on_auto'] * 100:.1f}% error",
                   xy=(o["review_load"] * 100, o["error_on_auto"] * 100),
                   xytext=(o["review_load"] * 100 - 27, 12.6), fontsize=6.4, color=INK2,
                   arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 0.7})

    a.set_xlim(0, 100)
    a.set_ylim(0, 17.5)  # the rule engine peaks at 15.8%: show all of it
    a.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    a.set_yticks([0, 5, 10, 15], ["0", "5", "10", "15%"])
    a.set_xlabel("Review load (share sent to a human)")
    a.set_ylabel("Error on automated decisions")
    a.set_title("(a)  Cost of meeting an error budget")

    # (b) Risk-coverage: does confidence rank correctness at all?
    for s in systems:
        pts = [(p["coverage"] * 100, p["risk"] * 100) for p in data[s]["risk_coverage"]]
        xs, ys = zip(*pts, strict=True)
        b.plot(xs, ys, color=COLOR[s], lw=1.6, marker=MARKER[s], ms=3.2, mec="white", mew=0.5,
               markevery=max(1, len(xs) // 8), zorder=3)
    if re_:
        rc = [(p["coverage"] * 100, p["risk"] * 100) for p in re_["risk_coverage"]]
        # Point at the first place the curve goes DOWN as coverage grows: that
        # is what "not monotone" looks like, and why no threshold rescues it.
        dip = next((i for i in range(1, len(rc)) if rc[i][1] < rc[i - 1][1] - 0.5), None)
        if dip is not None:
            b.annotate("not monotone:\nconfidence does not\nrank correctness",
                       xy=rc[dip], xytext=(rc[dip][0] + 6, rc[dip][1] + 15), fontsize=6.4,
                       color=INK2, arrowprops={"arrowstyle": "-", "color": AXIS, "lw": 0.7})
    b.set_xlim(0, 100)
    b.set_ylim(0, 60)
    b.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    b.set_yticks([0, 15, 30, 45, 60], ["0", "15", "30", "45", "60%"])
    b.set_xlabel("Coverage (most confident first)")
    b.set_ylabel("Error among covered")
    b.set_title("(b)  Risk–coverage")
    _system_legend(b, systems, loc="upper left", bbox_to_anchor=(0.0, 0.93), handletextpad=0.5)

    save(fig, "fig4_selective")


# --------------------------------------------------------------------------
# Figure 5 -- where the errors are
# --------------------------------------------------------------------------

PHENOMENA = (
    ("Cross-script name", (
        ("cross_script_name_alt_romanisation", "Alternative romanisation"),
        ("cross_script_name_icao", "ICAO romanisation"),
        ("cross_script_name_mismatch", "Different person's name"),
    )),
    ("Temporal", (
        ("temporal_consistent", "Consistent dates"),
        ("impossible_date_triple", "Impossible date triple"),
        ("date_off_by_one", "Date off by one day"),
    )),
    ("Evidence", (
        ("field_illegible", "Field illegible"),
        ("field_absent_from_document", "Field absent"),
    )),
)


def fig5_phenomena() -> None:
    data = _load("noise_robustness.json", "python scripts/noise_robustness.py")
    if data is None:
        return
    level = data.get("trained_at", "moderate")
    scored = data["levels"][level]
    systems = [s for s in SYSTEMS if s in scored]

    bar_h = 0.24
    rows: list[tuple[float, str, str]] = []  # (y, phenomenon key, display label)
    headers: list[tuple[float, str]] = []
    y = 0.0
    for family, items in PHENOMENA:
        # A header row per family, in the label column. Rotated labels in the
        # margin collided with each other: "Cross-script name" is taller than
        # the three rows it labels.
        headers.append((y, family))
        y += 0.85
        for key, label in items:
            rows.append((y, key, label))
            y += 1.0
        y += 0.25

    fig, ax = plt.subplots(figsize=(FULL_W, 3.0))
    centre = {}
    for yy, key, _ in rows:
        centre[key] = yy
        for k, s in enumerate(systems):
            acc = scored[s]["per_phenomenon_accuracy"].get(key, 0.0)
            offset = (k - (len(systems) - 1) / 2) * bar_h
            ax.barh(yy + offset, acc, height=bar_h, color=COLOR[s], edgecolor="white",
                    linewidth=0.9, zorder=3)

    # Value labels only where the story is: the model's misses.
    for key, yy in centre.items():
        if "cross_encoder" in systems:
            acc = scored["cross_encoder"]["per_phenomenon_accuracy"].get(key, 0.0)
            if acc < 0.995:
                offset = (systems.index("cross_encoder") - (len(systems) - 1) / 2) * bar_h
                # Past the LONGEST bar in the group, not the model's own: beside
                # its bar the label sat on the end of a longer neighbour.
                reach = max(scored[s]["per_phenomenon_accuracy"].get(key, 0.0) for s in systems)
                ax.text(reach + 0.012, yy + offset, f"{acc:.2f}", va="center", fontsize=6.4,
                        color=INK2)

    ax.set_yticks([r[0] for r in rows], [r[2] for r in rows])
    ax.invert_yaxis()
    ax.set_xlim(0, 1.08)
    ax.set_xticks([0, 0.25, 0.5, 0.75, 1.0], ["0", "0.25", "0.5", "0.75", "1.0"])
    ax.set_xlabel(f"Accuracy on held-out instances ({level} noise)")
    ax.grid(axis="y", visible=False)
    ax.tick_params(axis="y", length=0)

    for hy, family in headers:
        ax.text(-0.012, hy, family.upper(), transform=ax.get_yaxis_transform(),
                ha="right", va="center", fontsize=6.4, fontweight="bold", color=MUTED)
    ax.set_ylim(y - 0.25, -0.6)  # inverted: room above the first header

    _system_legend(ax, systems, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=3,
                   handletextpad=0.5, columnspacing=1.6)
    save(fig, "fig5_phenomena")


# --------------------------------------------------------------------------

FIGURES = {
    "task": fig1_task,
    "motivation": fig2_motivation,
    "noise": fig3_noise,
    "selective": fig4_selective,
    "phenomena": fig5_phenomena,
}


def main(argv: list[str]) -> int:
    style()
    wanted = argv or list(FIGURES)
    unknown = [w for w in wanted if w not in FIGURES]
    if unknown:
        print(f"Unknown figure(s) {unknown}. Choose from {list(FIGURES)}.")
        return 2
    for name in wanted:
        print(f"[{name}]")
        FIGURES[name]()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
