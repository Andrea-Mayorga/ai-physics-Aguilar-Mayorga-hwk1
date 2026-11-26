# Run from this folder. PYTHON can be overridden: make reproduce PYTHON=/path/to/python
PYTHON ?= python

.PHONY: reproduce test pipeline pipeline-refresh baseline notebook clean

reproduce:  ## Verify inputs, compute R (layer C), compare with P, write results/
	PYTHONPATH=src $(PYTHON) -m atmflux.reproduce

test:  ## Physics and reproducibility tests
	$(PYTHON) -m pytest -q

pipeline:  ## Data ingestion: verify raw cache (download only if needed), SQLite cache, provenance
	PYTHONPATH=src $(PYTHON) -m atmflux.data_pipeline_aguilar_mayorga

pipeline-refresh:  ## Same, downloading every input again from its original source
	PYTHONPATH=src $(PYTHON) -m atmflux.data_pipeline_aguilar_mayorga --refresh

baseline:  ## A0 baseline: 15 API calls (needs ANTHROPIC_API_KEY)
	PYTHONPATH=src $(PYTHON) -m atmflux.baseline_a0

notebook:  ## Re-execute the lab notebook in place (the kernel uses the same Python as $(PYTHON))
	PATH="$$(dirname "$$(command -v $(PYTHON))"):$$PATH" $(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace lab_notebook_aguilar_mayorga.ipynb

clean:  ## Remove generated outputs (inputs in data/ are never touched)
	rm -f results/R_values.json results/run_log.jsonl results/R_comparison.pdf
