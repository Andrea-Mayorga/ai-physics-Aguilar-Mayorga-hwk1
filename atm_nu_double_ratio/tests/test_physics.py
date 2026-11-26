"""Physics sanity tests. Run from the atm_nu_double_ratio folder with: make test"""

from pathlib import Path

import numpy as np
import pytest

from atmflux.compare import chi2, predict
from atmflux.honda import read_honda
from atmflux.oscillation import path_length, survival_probability
from atmflux.sk_data import read_sk_table

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def inputs():
    sk = {"numu": read_sk_table(DATA / "sk_numu_flux.csv"),
          "nue": read_sk_table(DATA / "sk_nue_flux.csv")}
    energies, blocks = read_honda(DATA / "honda2014_kamioka_cosz20_solmin.d.gz")
    return sk, energies, blocks


def test_path_length_limits():
    """From above L = h; from below L = 2R + h."""
    assert path_length(1.0) == pytest.approx(15.0)
    assert path_length(-1.0) == pytest.approx(2 * 6371.0 + 15.0)


def test_no_oscillation_without_distance():
    """If L = 0 there is no oscillation: P = 1."""
    assert survival_probability(1.0, 0.0, 2.5e-3, 1.0) == pytest.approx(1.0)


def test_input_tables(inputs):
    """Published sizes: 12 nu_mu bins, 11 nu_e bins; 20 Honda blocks."""
    sk, energies, blocks = inputs
    assert len(sk["numu"]["e2phi"]) == 12
    assert len(sk["nue"]["e2phi"]) == 11
    assert len(blocks) == 20
    assert energies.min() == pytest.approx(0.1)


def test_nue_agrees_without_oscillation(inputs):
    """nu_e barely oscillate at these energies: measured / predicted within 15%."""
    sk, energies, blocks = inputs
    ratio = sk["nue"]["e2phi"] / predict(energies, blocks, sk["nue"], "nue")
    assert np.all(np.abs(ratio - 1) < 0.15)


def test_oscillation_improves_numu_fit(inputs):
    """Oscillation must describe the nu_mu data much better than no oscillation."""
    sk, energies, blocks = inputs
    numu = sk["numu"]
    c2_no = chi2(numu["e2phi"], predict(energies, blocks, numu, "numu"), numu["err"])
    c2_osc = chi2(numu["e2phi"], predict(energies, blocks, numu, "numu", 2.5e-3, 1.0), numu["err"])
    ndf = len(numu["e2phi"])
    assert c2_no / ndf > 4
    assert c2_osc / ndf < 1.5
