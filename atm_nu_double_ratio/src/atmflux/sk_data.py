"""Step 1: read the atmospheric neutrino spectrum measured by Super-Kamiokande.

Source: Richard et al. (Super-Kamiokande), Phys. Rev. D 94, 052001 (2016),
tables published on HEPData (DOI 10.17182/hepdata.76912.v1).

Each table is a CSV with metadata lines starting with "#" and these columns:
bin centre in log10(E/GeV), lower edge, upper edge, E^2*Phi in
GeV cm^-2 s^-1 sr^-1, and the total error (statistical + systematic) in percent.
Super-K does not separate nu from nubar here: the values are nu + nubar.
"""

import csv
import io

import numpy as np


def read_sk_table(path):
    """Read a Super-K flux table and return a dictionary of NumPy arrays.

    Keys: "logE", "lo", "hi" (bins in log10(E/GeV)), "e2phi" (GeV cm^-2 s^-1 sr^-1)
    and "err" (absolute error, in the same units as "e2phi").
    """
    with open(path) as f:
        lines = [line for line in f if not line.startswith("#") and line.strip()]
    rows = list(csv.reader(io.StringIO("".join(lines))))[1:]  # [1:] skips the header
    table = np.array([[float(x.strip("%")) for x in row] for row in rows])
    return {
        "logE": table[:, 0],
        "lo": table[:, 1],
        "hi": table[:, 2],
        "e2phi": table[:, 3],
        "err": table[:, 4] / 100 * table[:, 3],  # from percent to absolute value
    }
