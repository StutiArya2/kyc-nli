"""Tests for the local web interface (`kyc-nli serve`).

The interface is run live in front of people, so like the terminal demo it is
tested for not falling over -- and, because it is a web server, for not serving
anything it should not. No gitignored data and no trained model are needed:
the backend takes injected instances and the two rule baselines.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from kyc_nli.app.server import Backend, _diff, make_handler
from kyc_nli.baselines import ExactMatchBaseline, RuleBaseline
from kyc_nli.data.generate import GeneratorConfig, InstanceGenerator
from kyc_nli.data.io import split_by_identity
from kyc_nli.languages import load_languages


def _split(noise: str):
    config = GeneratorConfig(
        languages=tuple(load_languages()), identities_per_language=3, noise_preset=noise, seed=9
    )
    return split_by_identity(InstanceGenerator(config).generate())["test"]


@pytest.fixture(scope="module")
def backend() -> Backend:
    b = Backend(splits={lv: _split(lv) for lv in ("clean", "moderate", "heavy")})
    b.systems = {"exact_match": ExactMatchBaseline(), "rule_engine": RuleBaseline()}
    b.loading = False
    return b


@pytest.fixture(scope="module")
def server(backend):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(backend))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def get(url: str):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def post(url: str, payload, raw: bytes | None = None):
    data = raw if raw is not None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# --------------------------------------------------------------------------
# The backend
# --------------------------------------------------------------------------


def test_the_same_document_exists_at_every_noise_level(backend) -> None:
    """The slider's whole premise. Same seed, same config, only noise differs."""
    ids = {lv: set(split) for lv, split in backend.splits.items()}
    assert ids["clean"] == ids["moderate"] == ids["heavy"]


def test_an_instance_carries_everything_the_page_draws(backend) -> None:
    some_id = next(iter(backend.splits["moderate"]))
    d = backend.instance("moderate", some_id)
    assert d is not None
    assert d["levels_available"] == ["clean", "moderate", "heavy"]
    assert d["premise"] and all("diff" in row for row in d["premise"])
    assert set(d["predictions"]) == {"exact_match", "rule_engine"}
    assert all(p["correct"] in (True, False) for p in d["predictions"].values())


def test_the_raw_mrz_block_is_drawn_as_a_strip_not_listed_as_a_field(backend) -> None:
    d = backend.instance("moderate", next(iter(backend.splits["moderate"])))
    assert all(row["field"] != "document_type" for row in d["premise"])
    assert d["mrz_lines"] and all(len(line) == 44 for line in d["mrz_lines"])


def test_at_clean_noise_the_only_damage_is_the_deliberately_destroyed_field(backend) -> None:
    """The control arm. At clean noise OCR changes nothing -- except that the
    field_illegible phenomenon destroys a field ON PURPOSE to build a NEUTRAL
    instance, whatever the noise level. Any other damage at clean would mean the
    noise preset is leaking into the control."""
    seen_illegible = False
    for inst_id, inst in backend.splits["clean"].items():
        damaged = [r for r in backend.instance("clean", inst_id)["premise"] if r["damaged"]]
        if inst.phenomenon == "field_illegible":
            seen_illegible = True
            assert len(damaged) == 1, f"{inst_id}: expected exactly the destroyed field"
        else:
            assert not damaged, f"{inst_id}: damaged at clean noise: {damaged}"
    assert seen_illegible, "precondition: the fixture contains a field_illegible instance"


def test_an_edited_claim_is_never_scored_against_the_original_gold(backend) -> None:
    """The original gold belongs to the original claim. Marking a verdict on an
    edited claim right or wrong would be inventing a label."""
    some_id = next(iter(backend.splits["moderate"]))
    out = backend.predict_edited("moderate", some_id, "SOMEBODY ELSE")
    assert "SOMEBODY ELSE" in out["text"]
    assert all(p["correct"] is None for p in out["predictions"].values())


def test_an_empty_edited_claim_is_refused(backend) -> None:
    with pytest.raises(ValueError):
        backend.predict_edited("moderate", next(iter(backend.splits["moderate"])), "   ")


def test_an_unknown_instance_is_none_not_an_exception(backend) -> None:
    assert backend.instance("moderate", "no-such-id") is None
    assert backend.instance("no-such-level", "x") is None


def test_predictions_made_while_loading_are_not_cached(backend) -> None:
    """Otherwise an instance viewed before the model loads lacks its verdict forever."""
    some_id = list(backend.splits["heavy"])[-1]
    backend.loading = True
    try:
        backend.instance("heavy", some_id)
        assert ("heavy", some_id) not in backend._cache
    finally:
        backend.loading = False
    backend.instance("heavy", some_id)
    assert ("heavy", some_id) in backend._cache


def test_the_diff_reconstructs_both_strings() -> None:
    """Every segment is accounted for: printed and observed can both be rebuilt."""
    clean, observed = "CHATTERJEE", "CHTTERJBF"
    segs = _diff(clean, observed)
    rebuilt_clean = "".join(s.get("was", s["text"]) for s in segs if s["op"] != "insert")
    rebuilt_obs = "".join(s["text"] for s in segs if s["op"] != "delete")
    assert rebuilt_clean == clean
    assert rebuilt_obs == observed
    assert any(s["op"] == "delete" for s in segs)


# --------------------------------------------------------------------------
# Over HTTP
# --------------------------------------------------------------------------


def test_the_page_and_api_are_served(server) -> None:
    status, ctype, body = get(server + "/")
    assert status == 200 and "text/html" in ctype and b"KYC-NLI" in body
    status, ctype, body = get(server + "/api/meta")
    meta = json.loads(body)
    assert status == 200 and "json" in ctype
    assert meta["levels"] == ["clean", "moderate", "heavy"]
    assert len(meta["languages"]) == 5


def test_the_listing_filters_by_language(server) -> None:
    _, _, body = get(server + "/api/instances?level=moderate&lang=ta")
    rows = json.loads(body)
    assert rows and all(r["language"] == "ta" for r in rows)


def test_non_latin_text_survives_the_json_round_trip(server, backend) -> None:
    """ensure_ascii would turn every Indic value into escapes the page must undo."""
    hi = next(i for i in backend.splits["moderate"] if i.startswith("hi-"))
    _, _, body = get(server + f"/api/instance?level=moderate&id={hi}")
    text = body.decode("utf-8")
    assert "\\u09" not in text  # Devanagari is U+0900-097F; no escapes
    assert any(0x900 <= ord(c) <= 0x97F for c in text)


@pytest.mark.parametrize(
    "path",
    [
        "/figures/../../pyproject.toml",
        "/figures/..%2F..%2Fpyproject.toml",
        "/figures/fig1_task.pdf",  # not on the whitelist: PNG only
        "/../../etc/passwd",
        "/static/index.html",  # the page is served at /, nothing else is a directory
    ],
)
def test_nothing_outside_the_whitelist_is_served(server, path) -> None:
    with pytest.raises(urllib.error.HTTPError) as err:
        get(server + path)
    assert err.value.code == 404


def test_an_oversized_request_body_is_refused(server) -> None:
    status, body = post(server + "/api/predict", None, raw=b"x" * 20_000)
    assert status == 413 and "error" in body


def test_malformed_json_is_an_error_not_a_crash(server) -> None:
    status, body = post(server + "/api/predict", None, raw=b"{not json")
    assert status in (400, 500) and "error" in body
    status, _, _ = get(server + "/api/meta")  # and the server is still up
    assert status == 200


def test_an_edited_claim_round_trips_over_http(server, backend) -> None:
    some_id = next(iter(backend.splits["moderate"]))
    status, body = post(server + "/api/predict",
                        {"id": some_id, "level": "moderate", "value": "PANDEY"})
    assert status == 200
    assert "PANDEY" in body["text"]
    assert set(body["predictions"]) == {"exact_match", "rule_engine"}


def test_the_server_binds_to_localhost_by_default() -> None:
    """Exposing a model server to the network should be a decision, not a default."""
    import inspect

    from kyc_nli.app import server as module

    assert inspect.signature(module.serve).parameters["host"].default == "127.0.0.1"
