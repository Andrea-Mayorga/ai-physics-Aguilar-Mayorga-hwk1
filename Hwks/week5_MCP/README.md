# Week 5 — MCP server for physics databases (SIMBAD + arXiv)

An MCP server that exposes two physics database queries as tools, and a Jupyter notebook in which an LLM (Claude) uses them in an agentic loop:

- `query_simbad(object_name)`: object type, spectral type, parallax and radial velocity from SIMBAD (via its TAP service, through `astroquery.simbad`).
- `search_arxiv(keyword, max_results)`: the most recent arXiv papers whose **abstracts** mention the keyword (title, authors, abstract, arXiv ID).

## How to reproduce

Clone the repository and go to this folder. Create the environment with conda (`conda env create -f environment.yml` and `conda activate mcp-physics`) or, with an existing Python 3.11 environment, run `pip install -r requirements.txt`. Copy the template with `cp .env.example .env` and write your Anthropic API key after `ANTHROPIC_API_KEY=` in `.env`; the key is only read from that file and `.env` is listed in `.gitignore`, so it is never committed. Before involving the LLM, you can check the tools directly with `python mcp_server_week05_Aguilar_Mayorga.py --test`, which queries Betelgeuse in SIMBAD and arXiv and makes no API calls. Then open `week05_Aguilar_Mayorga.ipynb`, select the kernel of the environment you created, and run all cells in order (Restart → Run All). You do not need to start the MCP server yourself: `run_agent` launches `mcp_server_week05_Aguilar_Mayorga.py` as a subprocess, connects to it over stdio (MCP handshake and `tools/list`), sends the tool schemas to Claude, and runs the agentic loop, printing every tool call (name, input arguments and full result), the model's summarized reasoning, and the token usage and estimated cost of each turn. If the server fails, its error messages are saved in `server_stderr.log`. One complete run of the notebook (Betelgeuse and TON 618) costs about US$0.03.

## Files

| File | Contents |
|---|---|
| `mcp_server_week05_Aguilar_Mayorga.py` | MCP server with the two tools and their JSON Schemas (`Annotated[..., Field(...)]`); `--test` runs the tools without an LLM |
| `week05_Aguilar_Mayorga.ipynb` | Agentic loop for Betelgeuse and TON 618, manual verification against SIMBAD web, consistency check of the LLM summaries against the abstracts, and physical plausibility check |
| `week05_failures_Aguilar_Mayorga.md` | Failure modes: SIMBAD down, ill-defined output for a non-stellar object, and a run with no visible output |
| `requirements.txt` / `environment.yml` | Dependencies with pinned versions (pip / conda) |
| `.env.example` | Template for the `.env` file with the API key |

## Versions

- Python 3.11.16
- `mcp` 2.2.0, `astroquery` 0.4.11, `astropy` 8.0.1, `arxiv` 4.0.1, `anthropic` 1.8.0, `pydantic` 2.13.5, `python-dotenv` 1.2.3, `numpy` 2.4.6, `ipykernel` 7.3.0

## LLM model and caveats

- **Model:** `claude-sonnet-5-5` (Claude Sonnet 5.5), set in the first cell of the notebook (`MODEL`).
- **Request parameters:** the loop uses `thinking={"type": "adaptive", "display": "summarized"}` and `output_config={"effort": "low"}`. These parameters depend on the model and the SDK version: with an older model or an older `anthropic` package they may be rejected, and with another model they may need to be changed.
- **Turn limit and costs:** the loop is capped at `MAX_TURNS = 5` LLM calls per question, with a 60 s timeout per call. The cost printed in each turn uses Sonnet 5.5 prices (US$2 / US$10 per million input / output tokens); it is an estimate, and it is wrong if you change the model.
- **Non-determinism:** the LLM's answers change from run to run (wording, level of detail, and even unsourced numbers; e.g. TON 618's black hole mass was given as ~4 × 10¹⁰ M☉ in one run and ~10¹⁰ M☉ in another). The consistency check in the notebook refers to the outputs saved in it.
- **Data that changes over time:** `search_arxiv` returns the *most recent* papers, so rerunning the notebook later may give different papers and therefore different summaries.
- **SIMBAD mirror:** the server points `astroquery` to the SIMBAD mirror at Harvard (`conf.server = "simbad.harvard.edu"`) because the main server in Strasbourg was down (see failure mode 1). The data are the same; once the main server is back, that line can be removed.
- **`mcp` 2.x:** this code uses the `mcp` 2.x API (`MCPServer`, `run_stdio_async()`, `input_schema`, `is_error`); `mcp` 1.x used different names (`inputSchema`, `isError`).
