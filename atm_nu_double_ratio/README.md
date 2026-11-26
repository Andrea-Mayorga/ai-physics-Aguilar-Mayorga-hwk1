# Reproducing the atmospheric-neutrino anomaly from public data, with and without AI

PHYS 7440 (Generative AI in Physics Research), final project. Author: Andrea Aguilar-Mayorga.
Status on 2026-11-25: **layer C complete and reproducible; layer A (AI agent) in progress.**

## Research question

The atmospheric-neutrino **double ratio**

$$R = \frac{(\mu/e)_\text{data}}{(\mu/e)_\text{prediction}}$$

equals 1 without oscillations. Kamiokande measured R ≈ 0.6, the first hint that ν_μ oscillate (into ν_τ).

**Question:** can an AI agent (`claude-opus-5-5`) that must *compose* the analysis from low-level MCP tools reproduce the R computed by my own code, from the same public data? or does it "cheat" by pretending to calculate it and just answering the user with its training knowledge? does this depend on the model and/or "effort" selected?


**Pass criterion (fixed in advance):** |R_A − R_C| / R_C ≤ 2 % in at least 80 % of 45 templated requests (15 templates × 3 runs), with a Wilson lower bound ≥ 65 %.

The project keeps three layers strictly separate:

| Layer | What it is | Role | Status |
|---|---|---|---|
| **P** | Published R: Super-K 2005 (Ashie et al.) and Kamiokande 1994 (Fukuda et al.), via PDG 2026 (ID S067DU0) | Validates C | Used only in the C-vs-P check |
| **C** | This Python package `atmflux`, **no AI at run time** | Reference ("truth") for A | ✅ Done (this README) |
| **A** | The agent with MCP tools; **A₀** = same model without tools (baseline) | What is evaluated | 🟡 Design done, implementation in progress |

**Precondition:** C agrees with the published Super-K R within 1σ, for both error bounds. **It holds** (see Expected outputs).
**Rule:** no AI system ever sees the published values. The MCP tools return *ingredients* (spectra, integrals); **no tool computes R and there is no calculator tool**. The agent must sum ν + ν̄, choose bins and weighting, form the ratios, propagate errors and do the arithmetic itself. Each agent answer must report its intermediate quantities and the expression it used, so that reasoning errors can be separated from arithmetic errors.

## Quick start (reproduce the main result)

```bash
git clone git@github.com:Andrea-Mayorga/ai-physics-Aguilar-Mayorga.git
cd ai-physics-Aguilar-Mayorga/atm_nu_double_ratio
conda env create -f environment.yml
conda activate atm-nu-double-ratio
make reproduce
make test
```

Without conda: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`, then `make reproduce`.
Runtime: under 2 seconds on a laptop. No internet access and **no API key** are needed: the input data are committed in `data/` and checked against their SHA-256.

## Expected outputs

`make reproduce` prints a summary and writes to `results/`:

| File | Content |
|---|---|
| `R_values.json` | Every R, both error bounds, every intermediate integral, the energy range actually used, the ν_e sanity ratios and the pulls vs. P. Deterministic: SHA-256 `044be30b1d143b58edb6fbbc99fb6feba64e6c9391e7ad156f5a0ef03330e383` with the pinned versions (other NumPy versions may change the last float digits; the values below are what matters). |
| `run_log.jsonl` | One JSON line per step (UTC time, step, status, elapsed ms, input hashes, versions). |
| `R_comparison.pdf` | Figure: published R vs. code R. Thick bars: uncorrelated errors; thin bars: fully correlated. |

Expected values (σ ∝ E weighting, the primary definition), to ±0.001:

| Sample | R_C | Error, uncorrelated – fully correlated | Exclusion of R = 1 | Pull vs Super-K 2005 | Pull vs Kamiokande 1994 |
|---|---|---|---|---|---|
| sub-GeV (0.1–1.33 GeV) | **0.595** | 0.069 – 0.141 | 5.9σ – 2.9σ | 0.80σ / 0.43σ | 0.05σ / 0.03σ |
| multi-GeV (1.33–30 GeV) | **0.701** | 0.077 – 0.172 | 3.9σ – 1.7σ | 0.01σ / 0.00σ | 1.00σ / 0.65σ |

Robustness (flux weighting, k = 0): R_sub = 0.572, R_multi = 0.695.
Published values: Super-K 0.658 ± 0.038 and 0.702 +0.106/−0.105; Kamiokande 0.60 +0.078/−0.071 and 0.57 +0.106/−0.099.
Every number above is traced to its output in [`claim_trace.md`](claim_trace.md).

**Physical result:** R = 1 is excluded in both samples. The difference between R_sub and R_multi (0.60 vs 0.70) is **not significant** and is not claimed as a result. The Super-K spectra and the Super-K R share the same detector, so that comparison is a consistency check; Kamiokande is independent.

## Physics definitions and approximations

- **Samples.** Sub-GeV (< 1.33 GeV) and multi-GeV (> 1.33 GeV): the Kamiokande convention inherited by Super-K; the PDG publishes R only for these. The outer limits 0.1 and 30 GeV are my choice.
- **Main approximation.** Super-K cuts on *visible* energy; this code cuts on *neutrino* energy.
- **Weighting.** Published R counts *events*; the inputs are *fluxes*. Primary ("sigma", k = 1): weight each neutrino by σ ∝ E as an event proxy (fixed before computing). Robustness check ("flux", k = 0): count every neutrino equally. Both are applied identically to Super-K and Honda.
- **Errors.** Super-K does not publish bin-to-bin correlations, so two bounds are reported: "none" (sum in quadrature, lower bound) and "full" (linear sum within each flavour, upper bound). Only the published Super-K errors are propagated; Honda's flux uncertainty is not included.
- **Bin clipping.** Bins that cross a sample limit are clipped. Because the ν_e table starts at 0.158 GeV and the ν_μ table at 0.251 GeV, the sub-GeV range actually used differs per flavour; `R_values.json` reports it (`range_used_gev`).
- **Within a Super-K bin**, E²Φ is taken as constant; the Honda prediction is the mean of its grid points inside each bin.

## Data (all public)

| File in `data/` | Source | Reference |
|---|---|---|
| `sk_numu_flux.csv`, `sk_nue_flux.csv` | HEPData `ins1401192`, Tables 2 and 1 | Richard et al. (Super-K), PRD 94, 052001 (2016), DOI 10.17182/hepdata.76912.v1 |
| `honda2014_kamioka_cosz20_solmin.d.gz` | http://www-rccn.icrr.u-tokyo.ac.jp/mhonda/public/nflx2014/ | Honda et al., PRD 92, 023004 (2015), HKKM2014 |

Exact URLs, access dates and SHA-256 hashes are in [`data/provenance.json`](data/provenance.json). Units: Super-K gives E²Φ in GeV cm⁻² s⁻¹ sr⁻¹ with ν + ν̄ combined and errors in %; Honda gives Φ in (m² s sr GeV)⁻¹ with ν and ν̄ separate. Conversion happens in `read_sk_table` (% → absolute) and `compare.to_sk_bins` (m⁻² → cm⁻², Φ → E²Φ).

**Safeguards in `make reproduce`:** (1) a hash mismatch or a truncated `.gz` stops the run and names the download URL; (2) a physics sanity check: ν_e barely oscillate, so measured/predicted ν_e must be within 0.8–1.2 in every bin (it is 0.87–1.05); a failure almost always means a unit error or a missing ν̄.

## Repository layout

```
atm_nu_double_ratio/
├── Makefile                 make reproduce | make test | make clean
├── data/                    public inputs + provenance.json (SHA-256)
├── results/                 outputs of make reproduce (+ numu_ratio.png from feasibility.py)
├── src/atmflux/
│   ├── sk_data.py           read Super-K tables
│   ├── honda.py             read Honda flux, average over zenith angle
│   ├── oscillation.py       two-flavour survival probability (feasibility study only)
│   ├── compare.py           Honda → Super-K bins, chi²
│   ├── double_ratio.py      integrals and R
│   ├── reproduce.py         one-command pipeline (layer C)
│   ├── proposal_figure.py   figure C vs P
│   └── feasibility.py       original feasibility check (chi², oscillation)
├── tests/                   pytest: physics limits, R definition, reproducibility
└── claim_trace.md           every quantitative claim → output file and key
```

## Tests

`make test` runs 14 tests: input table sizes, path-length limits, no oscillation at L = 0, ν_e agreement within 15 %, oscillation improves the ν_μ fit, R = 1 when data equal prediction, sub-GeV deficit, weighting change smaller than the error, full correlation never gives a smaller error, documented values, C-vs-P precondition, deterministic output, rejection of a corrupted input, and a complete run log.

## Randomness and secrets

- The analysis is **deterministic**: no random numbers, so there is no seed. `test_output_is_deterministic` checks byte-identical output.
- Layer C needs **no API key**. The future agent runs will read `ANTHROPIC_API_KEY` from the environment only; `.env` is git-ignored and [`.env.example`](.env.example) shows the variable name. No key is stored in any committed file.
- Agent runs are stochastic; each will be logged with model ID, effort level, tool-server version and input hashes (planned, week 10).

## What is not done yet

- MCP server `atmflux-mcp` with three tools (`get_sk_spectrum`, `get_honda_flux`, `integrate_spectrum`): designed, not implemented.
- The 45 templated requests, A₀ baseline, agent runs and failure taxonomy.
- Data pipeline extras: download with retries, raw cache, NaN sentinel for missing errors.


## AI use statement

Portions of this code and documentation were developed with Claude (Anthropic), through claude.ai and Claude Code, between October and November 2026. The author (human, Andrea Aguilar Mayorga) chose the research question, the project design based on the intended goal, the physics definitions, and the evaluation design. 

Every number reported here is produced by the code in this folder and checked by the tests and by the comparison with independent published values. Layer C uses no AI at run time.

## References

- Y. Fukuda et al. (Kamiokande), Phys. Lett. B 335, 237 (1994).
- Y. Ashie et al. (Super-Kamiokande), Phys. Rev. D 71, 112005 (2005).
- E. Richard et al. (Super-Kamiokande), Phys. Rev. D 94, 052001 (2016).
- M. Honda et al., Phys. Rev. D 92, 023004 (2015).
- Particle Data Group, Review of Particle Physics (2026).
