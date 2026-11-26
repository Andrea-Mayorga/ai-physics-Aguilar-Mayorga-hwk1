"""One-command reproduction of the code-only result (layer C) and its check against P.

Usage, from the project folder (atm_nu_double_ratio/):
    make reproduce
or
    PYTHONPATH=src python -m atmflux.reproduce

Steps:
  1. Verify every input file against the SHA-256 in data/provenance.json and check
     that the Honda .gz file decompresses completely (a truncated download fails here).
  2. Read the Super-K spectra and the Honda flux, and put Honda in the Super-K bins.
  3. Physics sanity check at run time: nu_e barely oscillates, so measured / predicted
     nu_e must lie within 0.8-1.2 in every bin. If not, it is almost always a unit
     mistake (m^2 vs cm^2, Phi vs E^2 Phi) or a missing nubar, and the run stops.
  4. Compute R for both samples, both weightings and both error bounds, keeping
     every intermediate integral, and compare C with the published values (P).
  5. Write results/R_values.json (deterministic: same inputs give the same file),
     results/run_log.jsonl (one JSON line per step, with timestamps and timings)
     and the figure results/R_comparison.pdf.

The analysis has no random numbers, so there is no seed to fix. No AI system is
involved here: this is layer C. The published values are used only in step 4.
"""

import gzip
import hashlib
import json
import platform
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .compare import predict
from .double_ratio import WEIGHTS, integrate
from .honda import read_honda
from .proposal_figure import PUBLISHED, SAMPLES
from .proposal_figure import main as make_figure
from .sk_data import read_sk_table

PROJECT = Path(__file__).resolve().parents[2]
NUE_SANITY_RANGE = (0.8, 1.2)
CORRELATIONS = ("none", "full")
PUBLISHED_KEYS = {"Kamiokande 1994": "Kamiokande 1994\n(published)",
                  "Super-K 2005": "Super-K 2005\n(published)"}


class RunLog:
    """Append one JSON object per step to a .jsonl file (structured log)."""

    def __init__(self, path):
        self.path = path
        self.path.write_text("")
        self.t0 = time.perf_counter()

    def write(self, step, status="ok", **details):
        entry = {"time_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "step": step, "status": status,
                 "elapsed_ms": round(1000 * (time.perf_counter() - self.t0), 1), **details}
        with self.path.open("a") as f:
            f.write(json.dumps(entry) + "\n")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_inputs(data_dir):
    """Step 1. Return {file: sha256}; raise RuntimeError on any mismatch."""
    records = json.loads((data_dir / "provenance.json").read_text())
    hashes = {}
    for rec in records:
        path = data_dir / rec["file"]
        if not path.exists():
            raise RuntimeError(f"Missing input {path}. Download it from {rec['source']}")
        digest = sha256(path)
        if digest != rec["sha256"]:
            raise RuntimeError(f"SHA-256 mismatch for {path.name}: expected {rec['sha256']}, "
                               f"got {digest}. Re-download it from {rec['source']}")
        if path.suffix == ".gz":
            with gzip.open(path) as f:  # raises EOFError/BadGzipFile if truncated
                f.read()
        hashes[rec["file"]] = digest
    return hashes


def load_inputs(data_dir):
    """Step 2. Super-K tables and Honda prediction in the Super-K bins (nu + nubar)."""
    sk = {"numu": read_sk_table(data_dir / "sk_numu_flux.csv"),
          "nue": read_sk_table(data_dir / "sk_nue_flux.csv")}
    energies, blocks = read_honda(data_dir / "honda2014_kamioka_cosz20_solmin.d.gz")
    predicted = {f: predict(energies, blocks, sk[f], f) for f in sk}
    return sk, predicted


def check_nue_sanity(sk, predicted):
    """Step 3. Return the per-bin nu_e ratios; raise RuntimeError if any is out of range."""
    ratio = sk["nue"]["e2phi"] / predicted["nue"]
    lo, hi = NUE_SANITY_RANGE
    bad = np.where((ratio < lo) | (ratio > hi))[0]
    if bad.size:
        raise RuntimeError(f"nu_e measured/predicted outside {NUE_SANITY_RANGE} in bins "
                           f"{bad.tolist()}: {ratio[bad].round(3).tolist()}. Check units "
                           "(m^-2 vs cm^-2, Phi vs E^2 Phi) and that nu + nubar are summed.")
    return ratio


def used_range(table, e_min, e_max):
    """Energy range (GeV) actually integrated: integrate() clips bins at the limits."""
    lo = max(10.0 ** table["lo"].min(), e_min)
    hi = min(10.0 ** table["hi"].max(), e_max)
    return [round(lo, 4), round(hi, 4)]


def double_ratio_detail(sk, predicted, e_min, e_max, weighting):
    """R with every intermediate quantity, for both error bounds.

    Same arithmetic as double_ratio.double_ratio, written out so that each number
    can later be compared with the intermediates the agent (layer A) reports.
    """
    out = {"weighting": weighting, "k": WEIGHTS[weighting],
           "range_requested_gev": [e_min, e_max],
           "range_used_gev": {f: used_range(sk[f], e_min, e_max) for f in sk}}
    for corr in CORRELATIONS:
        mu, mu_pred, mu_err = integrate(sk["numu"], predicted["numu"], e_min, e_max, weighting, corr)
        e, e_pred, e_err = integrate(sk["nue"], predicted["nue"], e_min, e_max, weighting, corr)
        r = (mu / e) / (mu_pred / e_pred)
        r_err = r * np.hypot(mu_err / mu, e_err / e)
        if corr == "none":
            out["integrals"] = {"numu_data": mu, "numu_pred": mu_pred,
                                "nue_data": e, "nue_pred": e_pred,
                                "ratio_data_mu_over_e": mu / e,
                                "ratio_pred_mu_over_e": mu_pred / e_pred}
            out["R"] = r
        out[f"error_{corr}"] = {"numu_data": mu_err, "nue_data": e_err, "R": r_err,
                                "exclusion_of_R1_sigma": (1 - r) / r_err}
    return out


def compare_with_published(r_c, err_c, published):
    """Pull |R_C - R_P| / sqrt(err_C^2 + err_P^2), using P's error on the side of R_C."""
    value, up, down = published
    err_p = up if r_c > value else down
    return abs(r_c - value) / np.hypot(err_c, err_p)


def run(data_dir=PROJECT / "data", out_dir=PROJECT / "results", figure=True):
    out_dir.mkdir(exist_ok=True)
    log = RunLog(out_dir / "run_log.jsonl")
    log.write("start", python=platform.python_version(), numpy=np.__version__,
              platform=platform.platform(terse=True))
    try:
        hashes = verify_inputs(data_dir)
        log.write("verify_inputs", files=hashes)
        sk, predicted = load_inputs(data_dir)
        log.write("load_inputs", numu_bins=len(sk["numu"]["e2phi"]), nue_bins=len(sk["nue"]["e2phi"]))
        ratio = check_nue_sanity(sk, predicted)
        log.write("nue_sanity", min_ratio=float(ratio.min()), max_ratio=float(ratio.max()))
    except Exception as exc:
        log.write("abort", status="error", error=f"{type(exc).__name__}: {exc}")
        raise

    results = {"description": "Layer C (code only, no AI): double ratio R = (mu/e)_data / "
                              "(mu/e)_prediction from Super-K unfolded spectra and HKKM2014.",
               "inputs_sha256": hashes,
               "nue_sanity_ratio_per_bin": ratio.tolist(),
               "samples": {}}
    for sample, (e_min, e_max) in SAMPLES.items():
        entry = {w: double_ratio_detail(sk, predicted, e_min, e_max, w) for w in WEIGHTS}
        primary = entry["sigma"]
        entry["pull_vs_published_sigma_weighting"] = {
            name: {corr: compare_with_published(primary["R"], primary[f"error_{corr}"]["R"],
                                                PUBLISHED[key][sample])
                   for corr in CORRELATIONS}
            for name, key in PUBLISHED_KEYS.items()}
        results["samples"][sample] = entry
    (out_dir / "R_values.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    log.write("compute_R", output="R_values.json")

    if figure:
        make_figure(str(out_dir / "R_comparison.pdf"), bracket=True, data_dir=data_dir)
        log.write("figure", output="R_comparison.pdf")
    log.write("done")
    return results


def summary(results):
    lines = ["sample      weighting  R      err(none)  err(full)  excl. R=1 (sigma)"]
    for sample, entry in results["samples"].items():
        for w in WEIGHTS:
            d = entry[w]
            lines.append(f"{sample:<11} {w:<10} {d['R']:.3f}  {d['error_none']['R']:.3f}      "
                         f"{d['error_full']['R']:.3f}      "
                         f"{d['error_full']['exclusion_of_R1_sigma']:.1f}-"
                         f"{d['error_none']['exclusion_of_R1_sigma']:.1f}")
    lines.append("Pull vs published (sigma weighting, err none / full):")
    for sample, entry in results["samples"].items():
        for name, p in entry["pull_vs_published_sigma_weighting"].items():
            lines.append(f"  {sample:<11} {name:<16} {p['none']:.2f} / {p['full']:.2f}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary(run()))
