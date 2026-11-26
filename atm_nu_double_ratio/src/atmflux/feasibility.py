"""Step 8: run the complete feasibility check.

Usage, from the atm_nu_double_ratio folder:
    PYTHONPATH=src python -m atmflux.feasibility
Prints the table of ratios and the chi^2 with and without oscillation, and saves
the figure to results/numu_ratio.png.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # save the figure to a file, without opening a window
import matplotlib.pyplot as plt

from .compare import chi2, p_value, predict
from .honda import read_honda
from .sk_data import read_sk_table

DATA = Path("data")
RESULTS = Path("results")
DM2_EV2 = 2.5e-3
SIN2_2THETA = 1.0


def main():
    sk = {"numu": read_sk_table(DATA / "sk_numu_flux.csv"),
          "nue": read_sk_table(DATA / "sk_nue_flux.csv")}
    energies, blocks = read_honda(DATA / "honda2014_kamioka_cosz20_solmin.d.gz")

    # Step 3: no oscillation. Sanity check: nu_e must give ratios close to 1.
    nue_ratio = sk["nue"]["e2phi"] / predict(energies, blocks, sk["nue"], "nue")
    print("nu_e  measured / Honda without oscillation:", nue_ratio.round(2))

    # Steps 4-6: nu_mu without and with oscillation.
    numu = sk["numu"]
    no_osc = predict(energies, blocks, numu, "numu")
    osc = predict(energies, blocks, numu, "numu", DM2_EV2, SIN2_2THETA)

    print("\n log10E   measured   no osc.    osc.       meas/no  meas/osc")
    for row in zip(numu["logE"], numu["e2phi"], no_osc, osc):
        log_e, m, p0, p1 = row
        print(f"{log_e:6.2f}  {m:.3e}  {p0:.3e}  {p1:.3e}   {m/p0:5.2f}    {m/p1:5.2f}")

    # Step 7: chi^2 (no fitted parameters, ndf = number of bins).
    ndf = len(numu["e2phi"])
    print()
    for name, pred in [("no oscillation", no_osc), ("oscillation", osc)]:
        c2 = chi2(numu["e2phi"], pred, numu["err"])
        print(f"{name:15s} chi2 = {c2:6.1f}  chi2/ndf = {c2/ndf:5.2f}  p = {p_value(c2, ndf):.1e}")

    # Step 8: figure of the measured / predicted ratio.
    RESULTS.mkdir(exist_ok=True)
    energy = 10 ** numu["logE"]
    fig, ax = plt.subplots(figsize=(7, 4))
    for pred, label, marker in [(no_osc, "Honda, no oscillation", "s"),
                                (osc, f"Honda with oscillation (Δm² = {DM2_EV2} eV², sin²2θ = {SIN2_2THETA})", "o")]:
        ax.errorbar(energy, numu["e2phi"] / pred, yerr=numu["err"] / pred,
                    fmt=marker, capsize=3, label=label)
    ax.axhline(1, color="gray", lw=1, ls="--")
    ax.set_xscale("log")
    ax.set_xlabel("Neutrino energy (GeV)")
    ax.set_ylabel("Super-K measured / predicted")
    ax.set_title("Atmospheric νμ + ν̄μ flux at Kamioka")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(RESULTS / "numu_ratio.png", dpi=150)
    print(f"\nFigure saved to {RESULTS / 'numu_ratio.png'}")


if __name__ == "__main__":
    main()
