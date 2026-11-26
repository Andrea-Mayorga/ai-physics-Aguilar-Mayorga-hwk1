"""Tests for the one-command reproduction (atmflux.reproduce)."""

import json
import shutil
from pathlib import Path

import pytest

from atmflux.reproduce import run, verify_inputs

DATA = Path(__file__).parent.parent / "data"

# Documented expected outputs (README "Expected outputs"), sigma weighting.
EXPECTED = {"sub-GeV": (0.595, 0.069, 0.141), "multi-GeV": (0.701, 0.077, 0.172)}


@pytest.fixture(scope="module")
def results(tmp_path_factory):
    return run(out_dir=tmp_path_factory.mktemp("results"), figure=False)


def test_documented_values(results):
    """R and both error bounds match the README to the quoted precision."""
    for sample, (r, err_none, err_full) in EXPECTED.items():
        d = results["samples"][sample]["sigma"]
        assert d["R"] == pytest.approx(r, abs=5e-4)
        assert d["error_none"]["R"] == pytest.approx(err_none, abs=5e-4)
        assert d["error_full"]["R"] == pytest.approx(err_full, abs=5e-4)


def test_precondition_c_agrees_with_published(results):
    """Precondition of the project: C within 1 sigma of Super-K 2005, both error bounds."""
    for sample in EXPECTED:
        pulls = results["samples"][sample]["pull_vs_published_sigma_weighting"]["Super-K 2005"]
        assert pulls["none"] <= 1.0 and pulls["full"] <= 1.0


def test_output_is_deterministic(tmp_path):
    """Same inputs give a byte-identical R_values.json (no timestamps, no randomness)."""
    run(out_dir=tmp_path / "a", figure=False)
    run(out_dir=tmp_path / "b", figure=False)
    assert (tmp_path / "a/R_values.json").read_bytes() == (tmp_path / "b/R_values.json").read_bytes()


def test_corrupted_input_is_rejected(tmp_path):
    """A modified data file must stop the run with a SHA-256 error, not give a number."""
    data = tmp_path / "data"
    shutil.copytree(DATA, data)
    with (data / "sk_nue_flux.csv").open("a") as f:
        f.write("\n")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        verify_inputs(data)


def test_log_records_every_step(tmp_path):
    run(out_dir=tmp_path, figure=False)
    steps = [json.loads(line)["step"] for line in (tmp_path / "run_log.jsonl").read_text().splitlines()]
    assert steps == ["start", "verify_inputs", "load_inputs", "nue_sanity", "compute_R", "done"]
