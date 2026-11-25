"""Specification-first tests for ai_generated_oscillator.py (Week 3).

Specification (dimensionless units, hbar = m = omega = 1, xi = x):
    E_n   = (n + 1/2) hbar omega                                   Griffiths eq. 2.50
    psi_n = (2^n n!)^(-1/2) pi^(-1/4) H_n(x) exp(-x^2/2)            Griffiths eq. 2.69
    H_n   = physicists' Hermite polynomials, e.g. H_2(x) = 4x^2 - 2
    <psi_m|psi_n> = delta_mn  (normalized and mutually orthogonal)
    main() plots the 5 lowest states n = 0..4 as |psi_n|^2.

Each test maps to one bug in week03_Aguilar-Mayorga_bugreport.md.
"""
import math

import numpy as np
import pytest

N_LEVELS = 5
ATOL_INTEGRAL = 1e-8  # trapezoid rule on x_grid is accurate to ~1e-15; 1e-8 leaves a wide safety margin


# --------------------------------------------------------------------------- #
# Bug #1 — wrong physics formula for the energy levels
# --------------------------------------------------------------------------- #
def test_energy_levels_match_griffiths(osc):
    """E_n = (n + 1/2) for n = 0..4 with hbar = omega = 1 (Griffiths eq. 2.50)."""
    expected = np.array([0.5, 1.5, 2.5, 3.5, 4.5])
    np.testing.assert_allclose(osc.energy_levels(), expected, rtol=1e-12)


def test_zero_point_energy_is_nonzero(osc):
    """The ground state has E_0 = hbar*omega/2 > 0 (zero-point energy), never 0."""
    assert osc.energy_levels()[0] == pytest.approx(0.5)


@pytest.mark.parametrize("hbar, omega", [(1.0, 1.0), (2.0, 3.0), (1.054571817e-34, 1.0e14)])
def test_energy_scales_with_hbar_omega(osc, hbar, omega):
    """E_n must scale as hbar*omega*(n + 1/2) for any physical values of hbar and omega."""
    expected = hbar * omega * (np.arange(N_LEVELS) + 0.5)
    np.testing.assert_allclose(osc.energy_levels(hbar=hbar, omega=omega), expected, rtol=1e-12)


# --------------------------------------------------------------------------- #
# Bug #3 — hallucinated API (special.hermite_poly); must use PHYSICISTS' H_n
# --------------------------------------------------------------------------- #
def test_harmonic_state_runs_and_returns_array(osc):
    """harmonic_state(n, x) must run (no AttributeError) and return one value per grid point."""
    x = np.linspace(-3, 3, 7)
    psi = osc.harmonic_state(2, x)
    assert np.shape(psi) == x.shape
    assert np.all(np.isfinite(psi))


def test_uses_physicists_hermite_n2(osc):
    """psi_2(x) * exp(x^2/2) must be proportional to H_2(x) = 4x^2 - 2 (physicists'),
    not to He_2(x) = x^2 - 1 (probabilists'). Comparing the *shape* (ratio to the value
    at x = 0) makes this test independent of the normalization constant."""
    x = np.array([-2.0, -1.0, -1 / np.sqrt(2), 0.0, 0.5, 1.0, 2.0])
    poly_part = osc.harmonic_state(2, x) * np.exp(x**2 / 2)      # = norm * H_2(x)
    H2 = 4 * x**2 - 2
    np.testing.assert_allclose(poly_part / poly_part[3], H2 / H2[3], rtol=1e-12, atol=1e-12)
    # H_2 vanishes at x = ±1/sqrt(2); He_2 would vanish at x = ±1 instead.
    assert poly_part[2] == pytest.approx(0.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# Bug #4 — incorrect normalization constant
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("n", range(N_LEVELS))
def test_states_are_normalized(osc, x_grid, n):
    """Integral of |psi_n|^2 over all x equals 1 for n = 0..4 (Griffiths eq. 2.69)."""
    psi = osc.harmonic_state(n, x_grid)
    assert np.trapezoid(np.abs(psi) ** 2, x_grid) == pytest.approx(1.0, abs=ATOL_INTEGRAL)


def test_ground_state_peak_value(osc):
    """psi_0(0) = pi^(-1/4): a pointwise check of the normalization, no integration needed."""
    assert osc.harmonic_state(0, np.array([0.0]))[0] == pytest.approx(np.pi ** -0.25, rel=1e-12)


# --------------------------------------------------------------------------- #
# Extra — orthogonality (of psi_n, i.e. of H_n with weight exp(-x^2))
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("m, n", [(m, n) for m in range(N_LEVELS) for n in range(m + 1, N_LEVELS)])
def test_states_are_orthogonal(osc, x_grid, m, n):
    """<psi_m|psi_n> = 0 for m != n. Since psi_m psi_n ∝ H_m H_n exp(-x^2), this is the
    orthogonality of the Hermite polynomials with weight exp(-x^2)."""
    overlap = np.trapezoid(osc.harmonic_state(m, x_grid) * osc.harmonic_state(n, x_grid), x_grid)
    assert overlap == pytest.approx(0.0, abs=ATOL_INTEGRAL)


def test_hermite_weighted_orthogonality_constants(osc, x_grid):
    """Full Gram matrix of H_n = psi_n * exp(x^2/2) / norm_n with weight exp(-x^2) must be
    diag(sqrt(pi) 2^n n!). Built from the module's psi_n, so it checks H_n and norm together."""
    norms = np.array([1 / math.sqrt(2**n * math.factorial(n) * math.sqrt(math.pi)) for n in range(N_LEVELS)])
    psis = np.array([osc.harmonic_state(n, x_grid) for n in range(N_LEVELS)])
    gram = np.trapezoid(psis[:, None, :] * psis[None, :, :], x_grid, axis=-1)   # <psi_m|psi_n>
    hermite_gram = gram / np.outer(norms, norms)                                 # ∫ H_m H_n e^{-x^2} dx
    expected = np.diag([math.sqrt(math.pi) * 2**n * math.factorial(n) for n in range(N_LEVELS)])
    np.testing.assert_allclose(hermite_gram, expected, atol=1e-6)


@pytest.mark.parametrize("n", range(N_LEVELS))
def test_parity(osc, n):
    """psi_n(-x) = (-1)^n psi_n(x): even states are symmetric, odd states antisymmetric."""
    x = np.linspace(0.1, 4.0, 40)
    np.testing.assert_allclose(osc.harmonic_state(n, -x), (-1) ** n * osc.harmonic_state(n, x), atol=1e-12)


# --------------------------------------------------------------------------- #
# Bug #2 — off-by-one: main() must plot all 5 states, starting at n = 0
# --------------------------------------------------------------------------- #
def test_main_plots_five_levels(plotted_lines):
    """main() draws exactly one curve per level n = 0..4."""
    assert len(plotted_lines) == N_LEVELS


def test_main_first_curve_is_ground_state(osc, plotted_lines):
    """The first curve is |psi_0|^2 (not psi_1): catches states[1:] even if labels say n=0."""
    line = plotted_lines[0]
    x = line.get_xdata()
    np.testing.assert_allclose(line.get_ydata(), np.abs(osc.harmonic_state(0, x)) ** 2, atol=1e-12)
    assert line.get_label() == "n=0"


# --------------------------------------------------------------------------- #
# Bug #5 — wrong output quantity: must plot |psi|^2, not psi
# --------------------------------------------------------------------------- #
def test_plotted_curves_are_probability_densities(osc, plotted_lines):
    """Every curve must equal |psi_n|^2: non-negative everywhere and matching the label's n."""
    for n, line in enumerate(plotted_lines):
        x, y = line.get_xdata(), line.get_ydata()
        assert np.all(y >= 0), f"curve n={n} has negative values: it is psi, not |psi|^2"
        np.testing.assert_allclose(y, np.abs(osc.harmonic_state(n, x)) ** 2, atol=1e-12)
