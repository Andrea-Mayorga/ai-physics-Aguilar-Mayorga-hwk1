"""Tests of the double ratio R. Run from the atm_nu_double_ratio folder with: make test"""

from pathlib import Path

import pytest

from atmflux.compare import predict
from atmflux.double_ratio import double_ratio
from atmflux.honda import read_honda
from atmflux.sk_data import read_sk_table

DATA = Path(__file__).parent.parent / "data"


@pytest.fixture(scope="module")
def inputs():
    sk = {"numu": read_sk_table(DATA / "sk_numu_flux.csv"),
          "nue": read_sk_table(DATA / "sk_nue_flux.csv")}
    energies, blocks = read_honda(DATA / "honda2014_kamioka_cosz20_solmin.d.gz")
    predicted = {f: predict(energies, blocks, sk[f], f) for f in sk}
    return sk, predicted


def test_r_is_one_when_data_equals_prediction(inputs):
    """If the 'measured' spectrum were exactly the prediction, R = 1 in any range."""
    sk, predicted = inputs
    fake = {f: dict(sk[f], e2phi=predicted[f]) for f in sk}
    for weighting in ["flux", "sigma"]:
        r, _ = double_ratio(fake, predicted, 0.1, 1.33, weighting)
        assert r == pytest.approx(1.0)


def test_sub_gev_deficit(inputs):
    """The nu_mu deficit must give R clearly below 1 under 1.33 GeV."""
    sk, predicted = inputs
    r, r_err = double_ratio(sk, predicted, 0.1, 1.33, "flux")
    assert r + 2 * r_err < 1.0


def test_definition_changes_are_small(inputs):
    """Changing the weighting (flux vs. cross section) moves R by less than its error."""
    sk, predicted = inputs
    for e_min, e_max in [(0.1, 1.33), (1.33, 30.0)]:
        r_flux, err = double_ratio(sk, predicted, e_min, e_max, "flux")
        r_sigma, _ = double_ratio(sk, predicted, e_min, e_max, "sigma")
        assert abs(r_sigma - r_flux) < err


def test_full_correlation_gives_larger_error(inputs):
    """Summing errors linearly (full correlation) never gives less error than in quadrature."""
    sk, predicted = inputs
    for e_min, e_max in [(0.1, 1.33), (1.33, 30.0)]:
        _, err_none = double_ratio(sk, predicted, e_min, e_max, "sigma", "none")
        _, err_full = double_ratio(sk, predicted, e_min, e_max, "sigma", "full")
        assert err_full >= err_none
