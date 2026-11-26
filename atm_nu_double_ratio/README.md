# Reproducing the atmospheric-neutrino anomaly from public data, with and without AI

PHYS 7440 (Generative AI in Physics Research), final project. Author: Andrea Aguilar-Mayorga.
Status on 2026-11-25: **layer C complete and reproducible; data ingestion pipeline (HW9) done; A₀ baseline run (0/15 answers within 2 %); agent with tools (layer A) in progress.**

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
| **A** | The agent with MCP tools; **A₀** = same model without tools (baseline) | What is evaluated | 🟡 A₀ run (`make baseline`, 0/15 within 2 %); agent with tools in progress |

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

Optional steps:

```bash
make pipeline          # data ingestion: verify the raw cache, build the SQLite cache, write provenance (no download if the cache is valid)
make pipeline-refresh  # same, but download every input again from its original source (needs internet and curl)
make baseline          # A0 baseline: 15 API calls to claude-opus-5-5 (needs ANTHROPIC_API_KEY; about 1-3 USD)
make notebook          # re-execute lab_notebook_aguilar_mayorga.ipynb
```

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

## Data ingestion pipeline (HW9)

`src/atmflux/data_pipeline_aguilar_mayorga.py` (`make pipeline`) takes the three inputs from **two external sources** (HEPData and Honda's ICRR page) through five steps:

1. **Fetch** with the system `curl` and `tenacity`: 3 retries with exponential backoff (1, 2, 4 s, capped at 30 s), only for transient errors. HEPData's Cloudflare front end answers HTTP 403 to Python's `urllib`, so `curl` is used as transport with its own user agent.
2. **Verify** the bytes against the SHA-256 registered in `data/provenance.json` (and decompress the `.gz` to detect truncation).
3. **Raw cache**: the verified files in `data/`. A valid cached file is not downloaded again unless `--refresh` is given; the cache is only (re)written with verified bytes, atomically.
4. **Normalize** to one internal schema: one row per (source, dataset, flavour, energy bin or grid point, zenith block), every flux as E²Φ in GeV cm⁻² s⁻¹ sr⁻¹ (Honda: ×E² ×10⁻⁴; Super-K errors: % → absolute).
5. **SQLite cache** `data/cache/atmflux_cache.sqlite` (table `measurements`, git-ignored, rebuilt in < 1 s) and the provenance record [`provenance_aguilar_mayorga.json`](provenance_aguilar_mayorga.json): source URL, access timestamp (or cache check), dataset version, SHA-256, transformations, row counts, git commit and package versions.

| Failure | What the code does | Test |
|---|---|---|
| Timeout, connection error, HTTP 429 or 5xx | Retry (4 attempts); if all fail, use the raw cache if its hash is valid, otherwise stop naming the URL | `test_transient_errors_are_retried`, `test_gives_up_after_three_retries`, `test_failed_download_falls_back_to_valid_cache`, `test_failed_download_without_cache_stops_with_url` |
| HTTP 404 and other non-transient errors | No retry | `test_not_found_is_not_retried` |
| Different SHA-256 or truncated `.gz` | Reject; the raw cache is not overwritten | `test_corrupt_download_is_rejected_and_cache_kept` |
| Missing or empty field | Warning with field, row and source URL; sentinel **NaN** (NULL in SQLite, field named in column `missing`); **never 0**, which would give a bin infinite weight | `test_missing_field_becomes_logged_sentinel`, `test_sentinel_is_null_in_sqlite` |

Both consumers see the same numbers: `test_cache_matches_the_readers_used_by_layer_c` checks that the SQLite cache equals, value by value, what layer C reads. On 2026-11-25 all three inputs were downloaded again and were byte-identical to the copies registered on 2026-10-13; no field is missing.

The lab notebook [`lab_notebook_aguilar_mayorga.ipynb`](lab_notebook_aguilar_mayorga.ipynb) shows the raw output of a real HEPData call, its normalized version, the SQLite cache, the layer-C result and the A₀-vs-C comparison.

## A₀ baseline (model without tools)

`src/atmflux/baseline_a0.py` (`make baseline`) sends 5 requests (sub-GeV, multi-GeV and 0.1–30 GeV; σ and flux weightings) × 3 runs to `claude-opus-5-5` with effort `medium` (set explicitly) and adaptive thinking with `display: "summarized"`, **without tools or data**. Each answer must end with a JSON object (R, R_err, expression, intermediates, assumptions, source of the numbers). Everything is stored in `results/a0_baseline.json`, including the thinking summary and token usage, next to R_C for the same request. The prompts never contain published values (`test_prompts_never_contain_published_values`). `--dry-run` prints the prompts without calling the API.

**Result (run of 2026-11-26 UTC, 15 calls, 8,619 input + 67,036 output tokens, about 1.4 USD):** 0 of 15 answers fall within 2 % of R_C. All 15 label their numbers as `estimated` (a self-report, not evidence of how the numbers were produced). 13 answers give R between 0.87 and 1.00; 8 of them state that the Super-K unfolded spectra are oscillation-corrected, and the other 5 take data ≈ HKKM. The 2 answers that state the spectra include oscillations give 0.69 (R_C = 0.595) and 0.72 (R_C = 0.701). The 8 statements are wrong for this paper: Richard et al. convert the unfolded event counts to flux with the oscillated HKKM11 flux at the SK site (their Eqs. 3.7–3.8), and the result agrees with the oscillated prediction, with the ν_μ deficit visible (Sec. III D, Fig. 7). Still, this is a pattern over 15 answers: the prompt does not say whether the spectra include oscillations, and this run cannot tell a wrong belief from a preference for R ≈ 1, nor computation from recall (near R_C, R_C and the published value are close). The stated uncertainties (R_err 0.06–0.15) cover the difference from R_C in only 1 of 15 answers. This run used `anthropic` SDK 1.6.0 (recorded in the JSON), not the pinned 1.8.0. Details and plot: section 4 of the lab notebook.

## Repository layout

```
atm_nu_double_ratio/
├── Makefile                 make reproduce | test | pipeline | baseline | notebook | clean
├── data/                    public inputs (= raw cache) + provenance.json (expected SHA-256); cache/ (SQLite, git-ignored)
├── results/                 outputs of make reproduce (+ numu_ratio.png from feasibility.py, a0_baseline.json)
├── provenance_aguilar_mayorga.json   provenance record of the last pipeline run
├── lab_notebook_aguilar_mayorga.ipynb  raw API output, normalized data, first results, A0 vs C
├── src/atmflux/
│   ├── sk_data.py           read Super-K tables
│   ├── honda.py             read Honda flux, average over zenith angle
│   ├── oscillation.py       two-flavour survival probability (feasibility study only)
│   ├── compare.py           Honda → Super-K bins, chi²
│   ├── double_ratio.py      integrals and R
│   ├── reproduce.py         one-command pipeline (layer C)
│   ├── data_pipeline_aguilar_mayorga.py  ingestion: fetch, verify, cache, normalize, SQLite, provenance
│   ├── baseline_a0.py       A0 baseline (model without tools)
│   ├── proposal_figure.py   figure C vs P
│   └── feasibility.py       original feasibility check (chi², oscillation)
├── tests/                   pytest: physics limits, R definition, reproducibility, pipeline, A0 parsing
└── claim_trace.md           every quantitative claim → output file and key
```

## Tests

`make test` runs 28 tests, none of which uses the network or the API:
- **Physics and R (9):** input table sizes, path-length limits, no oscillation at L = 0, ν_e agreement within 15 %, oscillation improves the ν_μ fit, R = 1 when data equal prediction, sub-GeV deficit, weighting change smaller than the error, full correlation never gives a smaller error.
- **Reproduction (5):** documented values, C-vs-P precondition, deterministic output, rejection of a corrupted input, complete run log.
- **Data pipeline (11):** the failure modes in the table above, no request when the cache is valid, cache equal to layer C's readers, complete provenance.
- **A₀ script (3):** final-JSON parsing and no published value in any prompt.

## Randomness and secrets

- The analysis is **deterministic**: no random numbers, so there is no seed. `test_output_is_deterministic` checks byte-identical output.
- Layer C and the data pipeline need **no API key**. `make baseline` (and the future agent runs) read `ANTHROPIC_API_KEY` from the environment, or from a git-ignored `.env` via `python-dotenv`; [`.env.example`](.env.example) shows the variable name. No key is stored in any committed file, and the script stops before sending anything if the key is missing.
- Model runs are stochastic and cannot be seeded; reproducibility comes from recording everything: `results/a0_baseline.json` stores the model ID, effort, thinking mode, SDK version, prompts, full answers, thinking summaries and token usage. Agent runs will also record the tool-server version and input hashes.

## What is not done yet

- MCP server `atmflux-mcp` with three tools (`get_sk_spectrum`, `get_honda_flux`, `integrate_spectrum`): designed, not implemented.
- The 45 templated requests, agent runs and failure taxonomy.


## AI use statement

Portions of this code and documentation were developed with Claude (Anthropic), through claude.ai and Claude Code, between October and November 2026. The author (human, Andrea Aguilar Mayorga) chose the research question, the project design based on the intended goal, the physics definitions, and the evaluation design. 

Every number reported here is produced by the code in this folder and checked by the tests and by the comparison with independent published values. Layer C uses no AI at run time.

## References

- Y. Fukuda et al. (Kamiokande), Phys. Lett. B 335, 237 (1994).
- Y. Ashie et al. (Super-Kamiokande), Phys. Rev. D 71, 112005 (2005).
- E. Richard et al. (Super-Kamiokande), Phys. Rev. D 94, 052001 (2016).
- M. Honda et al., Phys. Rev. D 92, 023004 (2015).
- Particle Data Group, Review of Particle Physics (2026).
