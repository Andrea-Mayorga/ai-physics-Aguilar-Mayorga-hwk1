"""Proposal figure: published R versus R computed by code only.

Usage, from the atm_nu_double_ratio folder:
    PYTHONPATH=src python -m atmflux.proposal_figure path/to/output.pdf [--bracket]

Published values taken from PDG 2026 (ID S067DU0):
    Super-K: Ashie et al. 2005 (INSPIRE 675543); Kamiokande: Fukuda et al. 1994 (INSPIRE 375027).
In the project, these values will be read from the `pdg` package; for now they are
hard-coded below (PUBLISHED). They are used only by layer C, for the C-vs-P check,
and are never exposed to the AI agent (no MCP tool returns them).
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .compare import predict
from .double_ratio import double_ratio
from .honda import read_honda
from .sk_data import read_sk_table

DATA = Path("data")
SAMPLES = {"sub-GeV": (0.1, 1.33), "multi-GeV": (1.33, 30.0)}
PUBLISHED = {  # (value, error+, error-)
    "Kamiokande 1994\n(published)": {"sub-GeV": (0.60, 0.078, 0.071), "multi-GeV": (0.57, 0.106, 0.099)},
    "Super-K 2005\n(published)": {"sub-GeV": (0.658, 0.038, 0.038), "multi-GeV": (0.702, 0.106, 0.105)},
}
CODE = {"Code, σ ∝ E\n(primary)": "sigma", "Code, flux\n(robustness)": "flux"}
STYLE = {"sub-GeV": ("o", "C0", -0.12), "multi-GeV": ("^", "C3", 0.12)}


def main(out_path, bracket=False, data_dir=DATA):
    """Draw the C-vs-P figure and save it to out_path.

    If bracket is True, the code rows also show (thin bar) the error with full
    bin-to-bin correlation; the thick bar is the uncorrelated error."""
    data_dir = Path(data_dir)
    sk = {"numu": read_sk_table(data_dir / "sk_numu_flux.csv"),
          "nue": read_sk_table(data_dir / "sk_nue_flux.csv")}
    energies, blocks = read_honda(data_dir / "honda2014_kamioka_cosz20_solmin.d.gz")
    predicted = {f: predict(energies, blocks, sk[f], f) for f in sk}

    rows = list(PUBLISHED) + list(CODE)
    fig, ax = plt.subplots(figsize=(3.4, 2.2))
    for sample, (e_min, e_max) in SAMPLES.items():
        marker, color, offset = STYLE[sample]
        for i, row in enumerate(rows):
            if row in PUBLISHED:
                v, up, down = PUBLISHED[row][sample]
                err = [[down], [up]]
            else:
                v, e = double_ratio(sk, predicted, e_min, e_max, CODE[row])
                err = [[e], [e]]
                if bracket:
                    _, e_full = double_ratio(sk, predicted, e_min, e_max, CODE[row], "full")
                    ax.errorbar(v, i + offset, xerr=[[e_full], [e_full]], fmt="none",
                                ecolor=color, elinewidth=0.6, alpha=0.6, capsize=1.5)
            ax.errorbar(v, i + offset, xerr=err, fmt=marker, color=color, capsize=2, ms=4,
                        label=sample if i == 0 else None)
    ax.set_yticks(range(len(rows)), rows, fontsize=7)
    ax.invert_yaxis()
    ax.axvline(1, color="gray", ls="--", lw=1)
    ax.set_xlim(0.35, 1.05)
    ax.set_xlabel(r"$R = (\mu/e)_\mathrm{data} / (\mu/e)_\mathrm{prediction}$", fontsize=8)
    ax.tick_params(axis="x", labelsize=7)
    ax.legend(fontsize=7, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_path, dpi=200)
    print(f"Saved {out_path}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(args[0] if args else "results/R_comparison.pdf", bracket="--bracket" in sys.argv)
