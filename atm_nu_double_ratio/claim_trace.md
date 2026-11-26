# Claim trace

Every quantitative claim in `README.md` → the output that produces it. All outputs come from `make reproduce` (module `atmflux.reproduce`) unless stated otherwise. JSON paths refer to `results/R_values.json`; `S` stands for `samples.<sample>`.

| # | Claim (README) | Value | Output file → key | Produced by | Checked by test |
|---|---|---|---|---|---|
| 1 | R_C, sub-GeV, σ weighting | 0.595 | `S."sub-GeV".sigma.R` | `reproduce.double_ratio_detail` | `test_documented_values` |
| 2 | Its error, uncorrelated / fully correlated | 0.069 / 0.141 | `…sigma.error_none.R`, `…sigma.error_full.R` | same | `test_documented_values` |
| 3 | Exclusion of R = 1, sub-GeV | 5.9σ / 2.9σ | `…sigma.error_none.exclusion_of_R1_sigma`, `…error_full…` | same | — (derived from 1–2) |
| 4 | R_C, multi-GeV, σ weighting | 0.701 | `S."multi-GeV".sigma.R` | same | `test_documented_values` |
| 5 | Its error, uncorrelated / fully correlated | 0.077 / 0.172 | `…sigma.error_none.R`, `…sigma.error_full.R` | same | `test_documented_values` |
| 6 | Exclusion of R = 1, multi-GeV | 3.9σ / 1.7σ | `…sigma.error_*.exclusion_of_R1_sigma` | same | — |
| 7 | Flux weighting: R_sub, R_multi | 0.572, 0.695 | `S."sub-GeV".flux.R`, `S."multi-GeV".flux.R` | same | `test_definition_changes_are_small` (difference < error) |
| 8 | Pull vs Super-K 2005 (sub, multi), errors none / full | 0.80 / 0.43; 0.01 / 0.00 | `S.<sample>.pull_vs_published_sigma_weighting."Super-K 2005"` | `reproduce.compare_with_published` | `test_precondition_c_agrees_with_published` (≤ 1σ) |
| 9 | Pull vs Kamiokande 1994 (sub, multi) | 0.05 / 0.03; 1.00 / 0.65 | `…"Kamiokande 1994"` | same | — |
| 10 | ν_e measured / predicted in every bin | 0.87–1.05 | `nue_sanity_ratio_per_bin`; also `results/run_log.jsonl`, step `nue_sanity` | `reproduce.check_nue_sanity` (stops the run outside 0.8–1.2) | `test_nue_agrees_without_oscillation` (within 15 %) |
| 11 | Sub-GeV range actually used: ν_e 0.158–1.33 GeV, ν_μ 0.251–1.33 GeV | — | `S."sub-GeV".<weighting>.range_used_gev` | `reproduce.used_range` | — |
| 12 | 12 ν_μ bins, 11 ν_e bins, 20 Honda zenith blocks | — | `run_log.jsonl`, step `load_inputs` | `reproduce.load_inputs` | `test_input_tables` |
| 13 | Input files match their published hashes | SHA-256 in `data/provenance.json` | `inputs_sha256`; `run_log.jsonl`, step `verify_inputs` | `reproduce.verify_inputs` | `test_corrupted_input_is_rejected` |
| 14 | Output is deterministic | SHA-256 of `R_values.json` in README | `results/R_values.json` | `reproduce.run` | `test_output_is_deterministic` |
| 15 | Figure C vs P | — | `results/R_comparison.pdf` | `proposal_figure.main(bracket=True)` | — (visual) |

**Published values (layer P)** quoted in the README and used for the pulls are hard-coded in `src/atmflux/proposal_figure.py` (`PUBLISHED`), transcribed from PDG 2026, ID S067DU0. They are inputs to the C-vs-P check only and are never available to the AI agent.

## Corrections to earlier documents

- The proposal v4 (written and slides) states that the flux-weighted R "differs by < 0.3σ" from the primary one. Measured: sub-GeV |ΔR| = 0.023, which is **0.34σ** in units of the primary (σ-weighted) uncorrelated error and 0.29σ in units of the flux-weighted error; multi-GeV |ΔR| = 0.006 (0.07σ). The README therefore makes no "< 0.3σ" claim.

## Claims from earlier documents not yet traced to an output

These appear in the proposal or in my notes but are **not** produced by `make reproduce`; they are not repeated in the README until a script produces them:

- Range of R_sub (0.565–0.610) and R_multi (0.689–0.704) when varying weightings and cuts.
- Effect of forgetting ν̄ on R_sub (0.630 both flavours; 1.180 only μ; 0.318 only e), intended to classify agent errors.
