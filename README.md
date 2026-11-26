# ai-physics-Aguilar-Mayorga

**Course:** PHYS 7440 — Generative AI in Physics Research  
**Student:** Andrea Aguilar Mayorga  
**Institution:** University of Manitoba

> **Final project → [`atm_nu_double_ratio/`](atm_nu_double_ratio/README.md)**: *Reproducing the atmospheric-neutrino anomaly from public data, with and without AI*. One-command reproduction: `cd atm_nu_double_ratio && make reproduce`.

## Contains:

* README: explaining a general overview of the repository
* .gitignore : file listing the files to ignore by github when pushing my initial commit. It allows me to add the API KEY to an .env to use it in the .ipynb, but not uploading it to keep it private (it exists locally in my laptop, but not in the public repository)
* .environment.yml: file containing all the necesary details to replicate the used environment in case anyone else wants to use this repository. It makes it easier for that new user to replicate my environment by just adding the following commands in their terminal:
conda env create -f environment.yml
conda activate ai-physics

---

* Week_02_Aguilar-Mayorga.ipynb: Main assignment notebook

## Overview

This notebook explores querying a large language model (Claude, via the Anthropic API) with physics questions and critically evaluating the quality of its responses against primary sources.

## Setup

```bash
conda env create -f environment.yml
conda activate ai-physics
jupyter notebook
```

Create a `.env` file in the root of the repo (never committed):

ANTHROPIC_API_KEY=your-key-here


## Notebook Structure

### 1. Environment setup
Loads the API key from `.env` using `python-dotenv` and initializes the Anthropic client.

### 2. `query_llm()` function
A reusable function that sends a prompt to a Claude model and returns the text response:

```python
def query_llm(prompt, model="claude-opus-4-5", max_tokens=1024):
    message = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text
```

### 3. Physics questions (4 total)

| # | Topic | Verification source |
|---|-------|---------------------|
| 1 | Conjugate variables and CSCO in quantum mechanics | Sakurai, *Modern Quantum Mechanics* |
| 2 | Heat vs. temperature from a thermodynamic perspective | Kondepudi & Prigogine; Fermi; Callen |
| 3 | Best PDG 2026 cosmic-ray supermassive monopole flux limit | PDG (model correctly admitted it lacked 2026 data) |
| 4 | Limitations of SR that motivated GR | Misner, Thorne & Wheeler, *Gravitation* (MTW) |

### 4. Performance review
Each answer is compared against the accepted value from a textbook or database:
- **Q1:** Correct and consistent with standard QM literature.
- **Q2:** Technically correct from a statistical mechanics viewpoint, but the explicitly thermodynamic framing was not fully honored — marked as *approximately correct*.
- **Q3:** Model correctly acknowledged it lacks access to 2026 PDG data — no hallucination.
- **Q4:** Core ideas are sound but omits the locality qualifier of the equivalence principle as stated in MTW §6.2 — marked as *approximately correct*.

### 5. Extra: Temperature in LLMs (informal exploration)
Documents why the same question yields different answers on each run (stochastic sampling), explains the temperature parameter conceptually, and records the discovery that `anthropic` v1.8.0 does not expose `temperature` in `messages.create()` — confirmed via `inspect.signature()`.

## Security Note

The `.gitignore` was committed **before** the `.env` file was created, ensuring the API key was never tracked by git at any point.

## Library version

anthropic==1.8.0
