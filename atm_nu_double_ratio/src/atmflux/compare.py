"""Steps 3, 6 and 7: bring the prediction to the Super-K bins and compare it with chi^2."""

import numpy as np
from scipy.stats import chi2 as chi2_distribution

from .honda import angle_average
from .oscillation import survival_in_block

FLAVORS = {"numu": ["numu", "numubar"], "nue": ["nue", "nuebar"]}


def to_sk_bins(energies, phi, sk_table):
    """Convert Honda's Phi to E^2*Phi in cm^-2 and average it within each Super-K bin.

    phi is in (m^2 s sr GeV)^-1; the factor 1e-4 converts m^-2 to cm^-2.
    The average uses the Honda grid points inside the bin (not an integral).
    """
    e2phi = energies**2 * phi * 1e-4
    log_e = np.log10(energies)
    values = []
    for lo, hi in zip(sk_table["lo"], sk_table["hi"]):
        inside = (log_e >= lo) & (log_e < hi)
        values.append(e2phi[inside].mean())
    return np.array(values)


def predict(energies, blocks, sk_table, flavor, dm2_ev2=None, sin2_2theta=None):
    """Prediction of E^2*Phi in the Super-K bins, with or without oscillation.

    If dm2_ev2 is None no oscillation is applied. The two-flavour oscillation is
    applied only to nu_mu (nu_e are left unchanged).
    """
    survival = None
    if dm2_ev2 is not None and flavor == "numu":
        def survival(c1, c2):
            return survival_in_block(energies, c1, c2, dm2_ev2, sin2_2theta)
    phi = angle_average(blocks, FLAVORS[flavor], survival)
    return to_sk_bins(energies, phi, sk_table)


def chi2(measured, predicted, err):
    """chi^2 treating the errors of each bin as independent."""
    return float(np.sum(((measured - predicted) / err) ** 2))


def p_value(chi2_value, ndf):
    """Probability of obtaining an equal or larger chi^2 if the model were correct."""
    return float(chi2_distribution.sf(chi2_value, ndf))
