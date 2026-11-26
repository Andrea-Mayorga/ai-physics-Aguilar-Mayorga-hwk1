"""Baseline A0: the same model as the agent, with no tools and no data files.

Usage, from the atm_nu_double_ratio folder (needs ANTHROPIC_API_KEY in the environment or in a
git-ignored .env file; costs roughly 1-3 USD for the default 5 requests x 3 runs):
    PYTHONPATH=src python -m atmflux.baseline_a0 --dry-run   # print the prompts, no API call
    PYTHONPATH=src python -m atmflux.baseline_a0             # run, write results/a0_baseline.json

A0 can only answer from what the model remembers or estimates, so comparing it with the code
reference R_C (layer C) measures how far the model gets without tools. The prompts never contain
the published R values (layer P). Each answer must end with a JSON object that reports R, the
expression used and the intermediate numbers, so reasoning errors can be told apart from
arithmetic errors. The thinking summary (display="summarized") is stored with every answer.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from .reproduce import PROJECT, double_ratio_detail, load_inputs

MODEL = "claude-opus-5-5"
EFFORT = "medium"  # set explicitly: it is the documented default for this model, recorded here
MAX_TOKENS = 16000
RUNS = 3
OUT = PROJECT / "results" / "a0_baseline.json"

REQUESTS = [  # id, e_min, e_max (GeV), weighting
    ("sub_sigma", 0.1, 1.33, "sigma"),
    ("multi_sigma", 1.33, 30.0, "sigma"),
    ("sub_flux", 0.1, 1.33, "flux"),
    ("multi_flux", 1.33, 30.0, "flux"),
    ("full_sigma", 0.1, 30.0, "sigma"),
]
WEIGHTING_TEXT = {
    "sigma": "weighting each neutrino by its energy (a cross section proportional to E, as a "
             "proxy for an event count), i.e. the integrals are of Phi(E) * E dE",
    "flux": "without any weighting (counting neutrinos), i.e. the integrals are of Phi(E) dE",
}
PROMPT = """You have no tools and no data files. Answer from your own knowledge.

Inputs to use:
- Measured: the Super-Kamiokande unfolded atmospheric-neutrino energy spectra of Richard et al., \
Phys. Rev. D 94, 052001 (2016) (HEPData record ins1401192): E^2 Phi for nu_mu + anti-nu_mu and \
for nu_e + anti-nu_e, in GeV cm^-2 s^-1 sr^-1, in bins of log10(E/GeV), with total errors.
- Predicted: the HKKM2014 flux (Honda et al., Phys. Rev. D 92, 023004 (2015)) at Kamioka, solar \
minimum, averaged over all directions, with nu and anti-nu summed.

Task: compute the double ratio R = (mu/e)_data / (mu/e)_prediction for neutrino energies \
{e_min} to {e_max} GeV, where mu and e are the integrals over that range of the nu + anti-nu flux \
of each flavour, {weighting_text}. Within each Super-K bin take E^2 Phi as constant. Estimate the \
uncertainty of R from the Super-K errors, assuming they are uncorrelated between bins.

State your assumptions and show your work; do the arithmetic yourself. End your answer with one \
JSON object in a ```json block with exactly these keys:
"R" (number), "R_err" (number or null), "expression" (string), "intermediates" (object of named \
numbers), "assumptions" (list of strings), "source_of_numbers" ("recalled", "estimated" or "computed")."""


def prompt_for(e_min, e_max, weighting):
    return PROMPT.format(e_min=e_min, e_max=e_max, weighting_text=WEIGHTING_TEXT[weighting])


def reference_values():
    """R_C for every request, from the verified inputs in data/ (layer C, no AI)."""
    sk, predicted = load_inputs(PROJECT / "data")
    return {rid: double_ratio_detail(sk, predicted, lo, hi, w)["R"] for rid, lo, hi, w in REQUESTS}


def parse_final_json(text):
    """Return (dict, None) from the last ```json block of text, or (None, reason)."""
    blocks = re.findall(r"```json\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if not blocks:
        return None, "no ```json block"
    try:
        obj = json.loads(blocks[-1])
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(obj.get("R"), (int, float)):
        return None, "missing numeric R"
    return obj, None


def ask(client, prompt):
    """One A0 request. Returns the answer text, the thinking summary and the metadata."""
    t0 = time.perf_counter()
    with client.messages.stream(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        thinking={"type": "adaptive", "display": "summarized"},
        output_config={"effort": EFFORT},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        message = stream.get_final_message()
    text = "".join(b.text for b in message.content if b.type == "text")
    thinking = "".join(b.thinking for b in message.content if b.type == "thinking")
    return {
        "text": text, "thinking_summary": thinking, "stop_reason": message.stop_reason,
        "model": message.model, "usage": {"input_tokens": message.usage.input_tokens,
                                          "output_tokens": message.usage.output_tokens},
        "elapsed_s": round(time.perf_counter() - t0, 1),
    }


def _load_key():
    """Read the API key from the environment, loading a git-ignored .env if python-dotenv exists."""
    try:
        from dotenv import find_dotenv, load_dotenv
        load_dotenv(find_dotenv(usecwd=True))
    except ImportError:
        pass
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set (see .env.example). Nothing was sent.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the A0 baseline (model without tools).")
    parser.add_argument("--runs", type=int, default=RUNS)
    parser.add_argument("--dry-run", action="store_true", help="print the prompts and R_C only")
    args = parser.parse_args(argv)

    r_c = reference_values()
    if args.dry_run:
        for rid, lo, hi, w in REQUESTS:
            print(f"--- {rid}  (R_C = {r_c[rid]:.4f})\n{prompt_for(lo, hi, w)}\n")
        print(f"{len(REQUESTS)} requests x {args.runs} runs = {len(REQUESTS) * args.runs} API calls")
        return

    _load_key()
    import anthropic
    client = anthropic.Anthropic()
    record = {"model": MODEL, "effort": EFFORT, "thinking": "adaptive, display=summarized",
              "max_tokens": MAX_TOKENS, "runs_per_request": args.runs,
              "anthropic_sdk": anthropic.__version__,
              "started_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "prompt_template": PROMPT, "requests": []}
    OUT.parent.mkdir(exist_ok=True)
    for rid, lo, hi, w in REQUESTS:
        entry = {"id": rid, "e_min_gev": lo, "e_max_gev": hi, "weighting": w,
                 "R_C": r_c[rid], "prompt": prompt_for(lo, hi, w), "runs": []}
        record["requests"].append(entry)
        for i in range(args.runs):
            answer = ask(client, entry["prompt"])
            parsed, problem = parse_final_json(answer["text"])
            answer.update(run=i, final_json=parsed, parse_error=problem,
                          R_A0=parsed["R"] if parsed else None,
                          rel_diff=abs(parsed["R"] - r_c[rid]) / r_c[rid] if parsed else None)
            entry["runs"].append(answer)
            OUT.write_text(json.dumps(record, indent=2) + "\n")  # save after every call
            shown = f"{answer['R_A0']:.3f}" if parsed else f"unparsed ({problem})"
            print(f"{rid:12s} run {i}: R_A0 = {shown}   R_C = {r_c[rid]:.3f}")
    record["finished_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    OUT.write_text(json.dumps(record, indent=2) + "\n")
    print(f"Saved {OUT.relative_to(PROJECT)}")


if __name__ == "__main__":
    main()
