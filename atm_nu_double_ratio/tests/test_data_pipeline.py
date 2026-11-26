"""Tests for the data ingestion layer (atmflux.data_pipeline_aguilar_mayorga).

No test touches the network: every download goes through a fake opener.
"""

import json
import logging
import math
import shutil
import sqlite3
import urllib.error
from pathlib import Path

import numpy as np
import pytest
from tenacity import wait_none

from atmflux import data_pipeline_aguilar_mayorga as dp
from atmflux.honda import COLUMNS as HONDA_COLUMNS
from atmflux.honda import read_honda
from atmflux.sk_data import read_sk_table

DATA = Path(__file__).parent.parent / "data"
INPUTS = ["provenance.json", "sk_numu_flux.csv", "sk_nue_flux.csv",
          "honda2014_kamioka_cosz20_solmin.d.gz"]


class FakeOpener:
    """Replays a list of outcomes: an exception is raised, bytes are returned."""

    def __init__(self, *outcomes):
        self.outcomes, self.calls = list(outcomes), 0

    def __call__(self, url, timeout):
        self.calls += 1
        outcome = self.outcomes[min(self.calls, len(self.outcomes)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def http_error(code):
    return urllib.error.HTTPError("https://example.org", code, f"HTTP {code}", None, None)


@pytest.fixture
def data_copy(tmp_path):
    """A private copy of the inputs, so tests can corrupt or delete files."""
    d = tmp_path / "data"
    d.mkdir()
    for name in INPUTS:
        shutil.copy(DATA / name, d / name)
    return d


def run_pipeline(data_dir, **kwargs):
    return dp.run(data_dir=data_dir, db_path=data_dir / "cache.sqlite",
                  provenance_path=data_dir / "prov.json", wait=wait_none(), **kwargs)


# ---- E1: timeouts and rate limits

def test_transient_errors_are_retried():
    opener = FakeOpener(http_error(503), http_error(429), b"payload")
    assert dp.fetch("u", opener=opener, wait=wait_none()) == b"payload"
    assert opener.calls == 3


def test_gives_up_after_three_retries():
    opener = FakeOpener(TimeoutError("slow server"))
    with pytest.raises(TimeoutError):
        dp.fetch("u", opener=opener, wait=wait_none())
    assert opener.calls == dp.RETRIES + 1 == 4


def test_not_found_is_not_retried():
    opener = FakeOpener(http_error(404))
    with pytest.raises(urllib.error.HTTPError):
        dp.fetch("u", opener=opener, wait=wait_none())
    assert opener.calls == 1


def test_failed_download_falls_back_to_valid_cache(data_copy):
    prov = run_pipeline(data_copy, refresh=True, opener=FakeOpener(ConnectionError("offline")))
    assert {d["access"]["status"] for d in prov["datasets"]} == {"download_failed_used_cache"}


def test_failed_download_without_cache_stops_with_url(data_copy):
    (data_copy / "sk_nue_flux.csv").unlink()
    with pytest.raises(RuntimeError, match="hepdata.net"):
        run_pipeline(data_copy, opener=FakeOpener(TimeoutError("slow server")))


def test_valid_cache_makes_no_request(data_copy):
    opener = FakeOpener(AssertionError("the network must not be used"))
    prov = run_pipeline(data_copy, opener=opener)
    assert opener.calls == 0
    assert {d["access"]["status"] for d in prov["datasets"]} == {"cache_hit"}


# ---- E2: integrity

def test_corrupt_download_is_rejected_and_cache_kept(data_copy):
    original = (data_copy / "sk_numu_flux.csv").read_bytes()
    bad = original.replace(b"1", b"2", 1)
    with pytest.raises(dp.IntegrityError, match="SHA-256 mismatch"):
        run_pipeline(data_copy, refresh=True, opener=FakeOpener(bad))
    assert (data_copy / "sk_numu_flux.csv").read_bytes() == original


# ---- E3: missing fields

def test_missing_field_becomes_logged_sentinel(caplog):
    csv_text = (b"# metadata line\n"
                b"log10(E),low,high,E2Phi,err\n"
                b"0.0,-0.1,0.1,1.0e-2,10%\n"
                b"0.2,0.1,0.3,8.0e-3,\n")  # second row: error missing
    url = "https://www.hepdata.net/test-table"
    with caplog.at_level(logging.WARNING, logger="atmflux.pipeline"):
        rows = dp.normalize_hepdata(csv_text, "sk_numu", url)
    assert rows[0]["error"] == pytest.approx(1.0e-3) and rows[0]["missing"] == ""
    assert math.isnan(rows[1]["error"]) and rows[1]["missing"] == "error_percent"
    assert rows[1]["error"] != 0
    assert "error_percent" in caplog.text and url in caplog.text


def test_sentinel_is_null_in_sqlite(tmp_path):
    row = dict(dp.normalize_hepdata(b"h,h,h,h,h\n0.0,-0.1,0.1,1e-2,\n", "sk_numu", "u")[0])
    registry = {"sk_numu": {"source": "u", "sha256": "x"}}
    dp.write_cache(tmp_path / "c.sqlite", {"sk_numu": [row]}, registry)
    con = sqlite3.connect(tmp_path / "c.sqlite")
    error, missing = con.execute("SELECT error, missing FROM measurements").fetchone()
    assert error is None and missing == "error_percent"


# ---- normalization: both consumers must see the same numbers

def test_cache_matches_the_readers_used_by_layer_c(data_copy):
    run_pipeline(data_copy)
    db = data_copy / "cache.sqlite"
    for dataset, file in [("sk_numu", "sk_numu_flux.csv"), ("sk_nue", "sk_nue_flux.csv")]:
        table = read_sk_table(DATA / file)
        rows = dp.read_cache(db, dataset)
        assert np.allclose([r["value"] for r in rows], table["e2phi"], rtol=1e-12)
        assert np.allclose([r["error"] for r in rows], table["err"], rtol=1e-12)
        assert np.allclose([math.log10(r["e_lo_gev"]) for r in rows], table["lo"], rtol=1e-12)
    energies, blocks = read_honda(DATA / "honda2014_kamioka_cosz20_solmin.d.gz")
    cached = {(r["cosz_min"], r["cosz_max"], r["flavor"], r["e_gev"]): r["value"]
              for r in dp.read_cache(db, "honda")}
    for c1, c2, table in blocks:
        for flavor, col in HONDA_COLUMNS.items():
            for e, phi in zip(energies, table[:, col]):
                assert cached[(min(c1, c2), max(c1, c2), flavor, e)] == pytest.approx(e**2 * phi * 1e-4)


def test_provenance_records_every_dataset(data_copy):
    run_pipeline(data_copy)
    prov = json.loads((data_copy / "prov.json").read_text())
    assert [d["dataset"] for d in prov["datasets"]] == ["sk_numu", "sk_nue", "honda"]
    for d in prov["datasets"]:
        assert d["source_url"].startswith("http") and len(d["sha256"]) == 64
        assert d["transformations"] and d["version"] and d["access"]["status"]
