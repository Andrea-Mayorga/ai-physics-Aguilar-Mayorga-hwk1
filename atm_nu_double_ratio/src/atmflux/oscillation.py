"""Steps 4 and 5: path length and nu_mu survival probability.

Two-flavour approximation in vacuum (no matter effects):
    P(nu_mu -> nu_mu) = 1 - sin^2(2 theta) * sin^2(1.267 * dm2[eV^2] * L[km] / E[GeV])
"""

import numpy as np

EARTH_RADIUS_KM = 6371.0
PRODUCTION_HEIGHT_KM = 15.0  # typical production height in the atmosphere


def path_length(cosz, radius=EARTH_RADIUS_KM, height=PRODUCTION_HEIGHT_KM):
    """Distance (km) from the production point to a detector at the surface.

    Law of cosines in the triangle Earth centre - detector - production point:
    L = sqrt((R + h)^2 - R^2 sin^2(theta)) - R cos(theta).
    """
    cosz = np.asarray(cosz, dtype=float)
    return np.sqrt((radius + height) ** 2 - radius**2 * (1 - cosz**2)) - radius * cosz


def survival_probability(energy_gev, length_km, dm2_ev2, sin2_2theta):
    """Two-flavour P(nu_mu -> nu_mu) in vacuum."""
    phase = 1.267 * dm2_ev2 * length_km / energy_gev
    return 1 - sin2_2theta * np.sin(phase) ** 2


def survival_in_block(energy_gev, cosz_min, cosz_max, dm2_ev2, sin2_2theta, n_samples=21):
    """P averaged within a cos(theta) block.

    At low energy and large L the phase changes very fast within the block, so
    evaluating only at the centre would give an arbitrary value. P is averaged
    over n_samples values of cos(theta) in the block.
    """
    cos_samples = np.linspace(cosz_min, cosz_max, n_samples)
    probs = [survival_probability(energy_gev, path_length(c), dm2_ev2, sin2_2theta)
             for c in cos_samples]
    return np.mean(probs, axis=0)
