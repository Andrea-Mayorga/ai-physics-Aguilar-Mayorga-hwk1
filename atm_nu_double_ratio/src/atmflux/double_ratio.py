"""Double ratio R = (mu/e)_measured / (mu/e)_predicted, at flux level.

The numerator uses the unfolded Super-K spectrum (HEPData) and the denominator the
Honda flux (HKKM2014) in the same bins. If neutrinos did not oscillate, R = 1.

Within each Super-K bin, E^2*Phi is taken as constant, so that
    integral of Phi(E) * E^k dE  =  Y * integral of E^(k-2) dE,   with Y = E^2*Phi.

Two weightings:
    k = 0  ("flux"):  counts neutrinos (R at flux level).
    k = 1  ("sigma"): weights by a cross section proportional to E, like a
                      charged-current event count (approximation valid above
                      ~1 GeV; below that, the truth lies between k = 0 and k = 1).

Bin-to-bin error correlation (Super-K does not publish it for these tables):
    "none": independent errors, summed in quadrature (reasonable lower bound).
    "full": errors fully correlated within each flavour, summed linearly
            (upper bound). The two flavours are treated as independent.
Reporting both gives an honest interval for the uncertainty on R.
"""

import numpy as np

WEIGHTS = {"flux": 0, "sigma": 1}


def _bin_weight(lo_log10, hi_log10, k):
    """Integral of E^(k-2) dE between 10**lo and 10**hi (E in GeV)."""
    e_lo, e_hi = 10.0**lo_log10, 10.0**hi_log10
    if k == 1:
        return np.log(e_hi / e_lo)
    return (e_hi ** (k - 1) - e_lo ** (k - 1)) / (k - 1)


def integrate(sk_table, predicted, e_min, e_max, weighting="flux", correlation="none"):
    """Integrate measured and predicted over [e_min, e_max] GeV.

    Returns (measured, predicted, error of measured). Bins that cross the limits
    are clipped; correlation chooses how the bin errors are combined.
    """
    k = WEIGHTS[weighting]
    lo_cut, hi_cut = np.log10(e_min), np.log10(e_max)
    measured = expected = variance = linear = 0.0
    for lo, hi, y, y_pred, err in zip(sk_table["lo"], sk_table["hi"], sk_table["e2phi"],
                                      predicted, sk_table["err"]):
        a, b = max(lo, lo_cut), min(hi, hi_cut)
        if b <= a:
            continue
        w = _bin_weight(a, b, k)
        measured += y * w
        expected += y_pred * w
        variance += (err * w) ** 2
        linear += err * w
    error = np.sqrt(variance) if correlation == "none" else linear
    return measured, expected, error


def double_ratio(sk, predicted, e_min, e_max, weighting="flux", correlation="none"):
    """R and its error over [e_min, e_max] GeV.

    sk: dictionary {"numu": table, "nue": table} from read_sk_table.
    predicted: dictionary {"numu": array, "nue": array} in the Super-K bins.
    The error propagates only the published Super-K errors, with the chosen correlation.
    """
    mu, mu_pred, mu_err = integrate(sk["numu"], predicted["numu"], e_min, e_max, weighting, correlation)
    e, e_pred, e_err = integrate(sk["nue"], predicted["nue"], e_min, e_max, weighting, correlation)
    r = (mu / e) / (mu_pred / e_pred)
    r_err = r * np.hypot(mu_err / mu, e_err / e)
    return r, r_err
