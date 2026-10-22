"""The local web interface behind ``kyc-nli serve``.

Standard library only -- no web framework -- because the interface must run
anywhere the pipeline runs, and a demo that needs one more ``pip install`` on
the presentation laptop is a demo that fails in front of the room.

What it shows that a slide cannot:

* **The same document at every noise level.** The noise-robustness splits hold
  the 1,050 held-out instances fixed and vary only the OCR damage, so one
  passport can be stepped from clean to heavy and all three systems re-decide
  on each.
* **A claim you can edit.** Change the hypothesis and every system is re-run
  live. An edited claim has no gold label, and the interface says so rather
  than inventing one.

Safety: binds to 127.0.0.1 by default, serves a fixed whitelist of files rather
than a directory, caps request bodies, and looks instances up by id in memory --
nothing a request sends is ever used as a path.
"""

from __future__ import annotations

import contextlib
import difflib
import json
import re
import threading
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from kyc_nli.baselines import NLISystem, available_systems
from kyc_nli.data.io import load_instances
from kyc_nli.languages import load_languages, repo_root
from kyc_nli.schema import Field, Hypothesis, Instance, Label, Script, Zone

STATIC = Path(__file__).parent / "static"
LEVELS = ("clean", "light", "moderate", "heavy")
MAX_BODY = 16_384
#: Below this OCR confidence a field is treated as unreadable by BOTH the rule
#: engine and the cross-encoder's serialiser; the interface marks it the same way.
ILLEGIBLE = 0.35

FIELD_ORDER = (
    Field.SURNAME, Field.GIVEN_NAMES, Field.DATE_OF_BIRTH, Field.DATE_OF_ISSUE,
    Field.DATE_OF_EXPIRY, Field.PLACE_OF_BIRTH, Field.ISSUING_AUTHORITY,
    Field.DOCUMENT_NUMBER, Field.NATIONALITY, Field.SEX, Field.TEMPLATE_ERA,
)
FIELD_LABEL = {
    Field.SURNAME: "Surname", Field.GIVEN_NAMES: "Given names",
    Field.DATE_OF_BIRTH: "Date of birth", Field.DATE_OF_ISSUE: "Date of issue",
    Field.DATE_OF_EXPIRY: "Date of expiry", Field.PLACE_OF_BIRTH: "Place of birth",
    Field.ISSUING_AUTHORITY: "Issuing authority", Field.DOCUMENT_NUMBER: "Document no.",
    Field.NATIONALITY: "Nationality", Field.SEX: "Sex", Field.TEMPLATE_ERA: "Template",
    Field.DOCUMENT_TYPE: "MRZ",
}
PHENOMENON_LABEL = {
    "cross_script_name_alt_romanisation": "Alternative romanisation",
    "cross_script_name_icao": "ICAO romanisation",
    "cross_script_name_mismatch": "Different person's name",
    "temporal_consistent": "Consistent dates",
    "impossible_date_triple": "Impossible date triple",
    "date_off_by_one": "Date off by one day",
    "field_illegible": "Field illegible",
    "field_absent_from_document": "Field absent",
}
_FIGURE_NAME = re.compile(r"^fig[0-9]_[a-z_]+\.png$")


def _diff(clean: str, observed: str) -> list[dict]:
    """What OCR did to a value, as display segments.

    Character-level, which is right for Latin text. For Indic and Perso-Arabic
    text the interface shows whole strings instead: splitting a word into
    differently-styled spans breaks the browser's shaping, and a vowel sign torn
    from its consonant would look like an OCR error that never happened.
    """
    segments: list[dict] = []
    matcher = difflib.SequenceMatcher(a=clean, b=observed, autojunk=False)
    for op, a0, a1, b0, b1 in matcher.get_opcodes():
        if op == "equal":
            segments.append({"op": "equal", "text": clean[a0:a1]})
        elif op == "delete":
            segments.append({"op": "delete", "text": clean[a0:a1]})
        elif op == "insert":
            segments.append({"op": "insert", "text": observed[b0:b1]})
        else:
            segments.append({"op": "replace", "text": observed[b0:b1], "was": clean[a0:a1]})
    return segments


class Backend:
    """Instances in memory, systems loaded once, predictions cached."""

    def __init__(self, splits: dict[str, list[Instance]] | None = None) -> None:
        """``splits`` maps a noise level to its instances; read from disk if omitted.

        Injectable so the tests need no gitignored data and no trained model.
        """
        root = repo_root()
        self.splits: dict[str, dict[str, Instance]] = {}
        if splits is not None:
            self.splits = {lv: {i.id: i for i in insts} for lv, insts in splits.items()}
        else:
            for level in LEVELS:
                path = root / "data" / "processed" / f"noise_{level}.test.jsonl"
                if path.exists():
                    self.splits[level] = {i.id: i for i in load_instances(path)}
            # Without the noise splits, fall back to the published test split at
            # its own noise level: a reduced interface beats no interface.
            if not self.splits:
                fallback = root / "data" / "processed" / "synth_v0.test.jsonl"
                if fallback.exists():
                    self.splits["moderate"] = {i.id: i for i in load_instances(fallback)}
        self.languages = load_languages()
        self.systems: dict[str, NLISystem] = {}
        self.notes: list[str] = []
        self.loading = True
        self._predict_lock = threading.Lock()
        self._cache: dict[tuple[str, str], dict] = {}
        self.results = self._load_results(root)

    # -- startup -----------------------------------------------------------

    def load_systems(self) -> None:
        """Run in a background thread: the page must not wait on torch."""
        try:
            for name, cls in available_systems().items():
                try:
                    self.systems[name] = cls()
                except Exception as exc:  # an untrained checkpoint, a missing extra
                    self.notes.append(f"{name} unavailable: {str(exc).splitlines()[0]}")
            if "cross_encoder" not in self.systems and not any(
                n.startswith("cross_encoder") for n in self.notes
            ):
                self.notes.append(
                    "cross_encoder is not trained -- run scripts/train_cross_encoder.py"
                )
        finally:
            self.loading = False

    @staticmethod
    def _load_results(root: Path) -> dict:
        out: dict = {}
        for key, name in (("noise", "noise_robustness.json"),
                          ("selective", "selective-prediction.json")):
            path = root / "results" / name
            if path.exists():
                # A half-written results file must not stop the interface opening.
                with contextlib.suppress(json.JSONDecodeError):
                    out[key] = json.loads(path.read_text(encoding="utf-8"))
        return out

    # -- queries -----------------------------------------------------------

    def meta(self) -> dict:
        any_split = next(iter(self.splits.values()), {})
        phenomena = sorted({i.phenomenon for i in any_split.values()})
        return {
            "levels": [lv for lv in LEVELS if lv in self.splits],
            "languages": [
                {"code": c, "name": s.name, "script": s.script.value}
                for c, s in self.languages.items()
            ],
            "phenomena": [{"key": p, "label": PHENOMENON_LABEL.get(p, p)} for p in phenomena],
            "systems": list(dict(self.systems)),
            "loading": self.loading,
            "notes": self.notes,
            "n_instances": len(any_split),
        }

    def listing(self, level: str, language: str, phenomenon: str, label: str) -> list[dict]:
        split = self.splits.get(level)
        if split is None:
            return []
        rows = []
        for inst in sorted(split.values(), key=lambda i: i.id):
            if language and inst.language != language:
                continue
            if phenomenon and inst.phenomenon != phenomenon:
                continue
            if label and inst.label.value != label:
                continue
            rows.append({
                "id": inst.id,
                "language": inst.language,
                "phenomenon": PHENOMENON_LABEL.get(inst.phenomenon, inst.phenomenon),
                "label": inst.label.value,
                "claim": inst.hypothesis.text,
            })
        return rows

    def instance(self, level: str, instance_id: str) -> dict | None:
        split = self.splits.get(level)
        inst = split.get(instance_id) if split else None
        if inst is None:
            return None
        return {
            "id": inst.id,
            "level": level,
            "levels_available": [lv for lv in LEVELS if instance_id in self.splits.get(lv, {})],
            "language": inst.language,
            "language_name": self.languages[inst.language].name,
            "phenomenon": PHENOMENON_LABEL.get(inst.phenomenon, inst.phenomenon),
            "gold": inst.label.value,
            "rationale": inst.rationale,
            "hypothesis": {
                "field": inst.hypothesis.field.value,
                "field_label": FIELD_LABEL.get(inst.hypothesis.field, inst.hypothesis.field.value),
                "value": inst.hypothesis.value,
                "text": inst.hypothesis.text,
            },
            "premise": self._premise(inst),
            "mrz_lines": next(
                (o.value.split("\n") for o in inst.premise if o.field is Field.DOCUMENT_TYPE),
                [],
            ),
            "predictions": self._predict(level, inst),
        }

    def predict_edited(self, level: str, instance_id: str, value: str) -> dict | None:
        """Re-run every system on the same document with a different claim."""
        from kyc_nli.data.generate import _verbalise

        split = self.splits.get(level)
        inst = split.get(instance_id) if split else None
        if inst is None:
            return None
        value = value.strip()[:120]
        if not value:
            raise ValueError("The claim value is empty.")
        h = inst.hypothesis
        edited = inst.model_copy(update={
            "id": f"{inst.id}::edited",
            "hypothesis": Hypothesis(
                field=h.field, value=value, script=h.script, language=h.language,
                text=_verbalise(h.field, value),
            ),
        })
        preds = self._run(edited, gold=None)
        return {"text": edited.hypothesis.text, "value": value, "predictions": preds}

    # -- internals ---------------------------------------------------------

    def _premise(self, inst: Instance) -> list[dict]:
        rows = []
        order = {f: n for n, f in enumerate(FIELD_ORDER)}
        for obs in sorted(
            (o for o in inst.premise if o.field is not Field.DOCUMENT_TYPE),
            key=lambda o: (0 if o.zone is Zone.VIZ else 1, order.get(o.field, 99)),
        ):
            clean = obs.clean_value if obs.clean_value is not None else obs.value
            rows.append({
                "field": obs.field.value,
                "field_label": FIELD_LABEL.get(obs.field, obs.field.value),
                "zone": obs.zone.value,
                "script": obs.script.value,
                "latin": obs.script is Script.LATIN,
                "observed": obs.value,
                "clean": clean,
                "confidence": round(obs.confidence, 3),
                "illegible": obs.confidence < ILLEGIBLE or not obs.value.strip(),
                "damaged": clean != obs.value,
                "diff": _diff(clean, obs.value),
            })
        return rows

    def _predict(self, level: str, inst: Instance) -> dict:
        # Never cache while systems are still loading: an instance viewed in the
        # first seconds would be stored without the model's verdict, for good.
        if self.loading:
            return self._run(inst, gold=inst.label)
        key = (level, inst.id)
        if key not in self._cache:
            self._cache[key] = self._run(inst, gold=inst.label)
        return self._cache[key]

    def _run(self, inst: Instance, gold: Label | None) -> dict:
        out = {}
        with self._predict_lock:  # torch is not something to call re-entrantly
            # A snapshot: the loader thread may still be adding systems.
            for name, system in list(self.systems.items()):
                p = system.predict(inst)
                out[name] = {
                    "label": p.label.value,
                    "confidence": round(p.confidence, 4),
                    "rationale": p.rationale,
                    "correct": None if gold is None else p.label is gold,
                }
        return out


def make_handler(backend: Backend) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "kyc-nli"

        def log_message(self, fmt, *args) -> None:  # quiet: the console is the demo
            return

        # -- plumbing ------------------------------------------------------

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, payload, status: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._send(status, body, "application/json; charset=utf-8")

        def _error(self, status: HTTPStatus, message: str) -> None:
            self._json({"error": message}, status=int(status))

        # -- routes --------------------------------------------------------

        def do_GET(self) -> None:  # noqa: N802 -- http.server's naming
            url = urlparse(self.path)
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path in ("/", "/index.html"):
                    html = (STATIC / "index.html").read_bytes()
                    self._send(200, html, "text/html; charset=utf-8")
                elif url.path == "/api/meta":
                    self._json(backend.meta())
                elif url.path == "/api/instances":
                    self._json(backend.listing(
                        q.get("level", "moderate"), q.get("lang", ""),
                        q.get("phenomenon", ""), q.get("label", ""),
                    ))
                elif url.path == "/api/instance":
                    data = backend.instance(q.get("level", "moderate"), q.get("id", ""))
                    if data is None:
                        self._error(HTTPStatus.NOT_FOUND, "No such instance at that level.")
                    else:
                        self._json(data)
                elif url.path == "/api/results":
                    self._json(backend.results)
                elif url.path.startswith("/figures/"):
                    name = url.path.rsplit("/", 1)[-1]
                    path = repo_root() / "paper" / "figures" / name
                    if _FIGURE_NAME.match(name) and path.is_file():
                        self._send(200, path.read_bytes(), "image/png")
                    else:
                        self._error(HTTPStatus.NOT_FOUND, "No such figure.")
                else:
                    self._error(HTTPStatus.NOT_FOUND, "Not found.")
            except Exception:  # a demo must report, never die
                traceback.print_exc()
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Server error; see the console.")

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path != "/api/predict":
                self._error(HTTPStatus.NOT_FOUND, "Not found.")
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY:
                self._error(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "Request body size rejected.")
                return
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                data = backend.predict_edited(
                    str(body.get("level", "moderate")), str(body.get("id", "")),
                    str(body.get("value", "")),
                )
                if data is None:
                    self._error(HTTPStatus.NOT_FOUND, "No such instance at that level.")
                else:
                    self._json(data)
            except ValueError as exc:
                self._error(HTTPStatus.BAD_REQUEST, str(exc))
            except Exception:
                traceback.print_exc()
                self._error(HTTPStatus.INTERNAL_SERVER_ERROR, "Server error; see the console.")

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8765, open_browser: bool = True) -> None:
    backend = Backend()
    threading.Thread(target=backend.load_systems, daemon=True).start()
    httpd = ThreadingHTTPServer((host, port), make_handler(backend))
    url = f"http://{host}:{port}/"
    print(f"KYC-NLI interface at {url}  (Ctrl+C to stop)")
    if not backend.splits:
        print("  no benchmark data found -- run `kyc-nli generate` first")
    if open_browser:
        import webbrowser

        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
