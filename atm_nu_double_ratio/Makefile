# Run from this folder. PYTHON can be overridden: make reproduce PYTHON=/path/to/python
PYTHON ?= python

.PHONY: reproduce test clean

reproduce:  ## Verify inputs, compute R (layer C), compare with P, write results/
	PYTHONPATH=src $(PYTHON) -m atmflux.reproduce

test:  ## Physics and reproducibility tests
	$(PYTHON) -m pytest -q

clean:  ## Remove generated outputs (inputs in data/ are never touched)
	rm -f results/R_values.json results/run_log.jsonl results/R_comparison.pdf
