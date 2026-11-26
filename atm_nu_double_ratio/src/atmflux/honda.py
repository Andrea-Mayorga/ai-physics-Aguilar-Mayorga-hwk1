"""Step 2: read the flux predicted by Honda (HKKM2014) and average it over directions.

Source: Honda et al., Phys. Rev. D 92, 023004 (2015). File for Kamioka without
mountain, azimuth-averaged, with 20 blocks in zenith cos(theta):
cos(theta) = +1 is a neutrino arriving from above and -1 one that crossed the Earth.

Each block starts with "average flux in [cosZ = a -- b, ...]" followed by rows:
E (GeV), nu_mu, nubar_mu, nu_e, nubar_e, in (m^2 s sr GeV)^-1.
Note: Honda uses m^-2 and Phi; Super-K uses cm^-2 and E^2*Phi.
"""

import gzip
import re

import numpy as np

COLUMNS = {"numu": 1, "numubar": 2, "nue": 3, "nuebar": 4}


def read_honda(path):
    """Return (E, blocks), where blocks is a list of (cosz_min, cosz_max, table).

    E is the energy grid in GeV (the same in every block) and each table
    has one row per energy and the columns in COLUMNS.
    """
    blocks, current = [], None
    with gzip.open(path, "rt") as f:
        for line in f:
            if line.startswith("average"):
                m = re.search(r"cosZ\s*=\s*([-\d.]+)\s*--\s*([-\d.]+)", line)
                current = [float(m.group(1)), float(m.group(2)), []]
                blocks.append(current)
            elif line.strip() and line.strip()[0].isdigit():
                current[2].append([float(x) for x in line.split()])
    blocks = [(c1, c2, np.array(rows)) for c1, c2, rows in blocks]
    energies = blocks[0][2][:, 0]
    return energies, blocks


def angle_average(blocks, flavors, survival=None):
    """Flux averaged over all directions, summing the given flavours.

    Each block has weight |delta cos(theta)| / 2: the solid angle of a block is
    proportional to its width in cos(theta), and the full interval [-1, 1] has width 2.
    If survival(c1, c2) is given, the flux of each block is multiplied by that
    probability (an array over the energy grid).
    Returns the flux in (m^2 s sr GeV)^-1.
    """
    total = 0.0
    for c1, c2, table in blocks:
        flux = sum(table[:, COLUMNS[f]] for f in flavors)
        if survival is not None:
            flux = flux * survival(c1, c2)
        total = total + flux * abs(c2 - c1)
    return total / 2
