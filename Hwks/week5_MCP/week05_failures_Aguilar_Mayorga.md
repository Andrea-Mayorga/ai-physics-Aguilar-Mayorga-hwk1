# Week 5 — Failure modes

Each failure mode records: the input that triggered it, the error or incorrect output produced, whether the agentic loop recovered or required manual intervention, and a proposed fix for a production system.

## 1. External service down: SIMBAD main server unavailable

- **Triggering input:**

  ```bash
  python mcp_server_week05_Aguilar_Mayorga.py --test
  ```

  which calls `query_simbad("Betelgeuse")`.

- **Error produced:**

  In October 2026, the main SIMBAD server (`simbad.cds.unistra.fr`) went down because of a security breach ([CDS announcement](https://bsky.app/profile/cdsportal.bsky.social/post/3myx3gzqoak2w)). Because of this, calling it resulted in a `404 Not Found` error for all of its endpoints, including the web interface and the TAP service, and `query_simbad` crashed before reaching the query itself (end of the traceback):

  ```
    File "/opt/anaconda3/envs/ai-physics/lib/python3.11/site-packages/pyvo/utils/decorators.py", line 9, in wrapper
      raw = func(*args, **kwargs)
            ^^^^^^^^^^^^^^^^^^^^^
    File "/opt/anaconda3/envs/ai-physics/lib/python3.11/site-packages/pyvo/dal/vosi.py", line 171, in _capabilities
      return self._get_endpoint('capabilities')
             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    File "/opt/anaconda3/envs/ai-physics/lib/python3.11/site-packages/pyvo/dal/vosi.py", line 122, in _get_endpoint
      raise DALServiceError(
  pyvo.dal.exceptions.DALServiceError: Unable to access the capabilities endpoint at:
  - https://simbad.cds.unistra.fr/simbad/sim-tap/capabilities: 404 Not Found
  - https://simbad.cds.unistra.fr/simbad/capabilities: 404 Not Found

  This could mean:
  1. The service URL is incorrect
  2. The service is temporarily unavailable
  3. The service doesn't support this protocol
  4. If a 503 was encountered, retry after the suggested delay.
  ```

- **Recovery:** manual intervention. The tool cannot work while the server is down, so I pointed astroquery to the official [SIMBAD mirror at Harvard](https://simbad.harvard.edu/simbad/) by adding the following to the imports section of the server:

  ```python
  from astroquery.simbad import conf
  conf.server = "simbad.harvard.edu"  # Use the SIMBAD mirror server when the main one is down
  ```

  `conf.server` is astroquery's real configuration parameter; `conf.servers_list` gives the official mirrors (`['simbad.cds.unistra.fr', 'simbad.harvard.edu']`).

- **Production fix:** catch service errors in `query_simbad` and automatically retry on the next server in `conf.servers_list`, returning a clear error to the LLM only if every mirror fails.

## 2. Non-stellar object: ill-defined tool output passed silently to the LLM

- **Context:** for the second object I deliberately chose TON 618, a hyperluminous quasar, and asked the same question as for Betelgeuse (a red supergiant). The goal was to see how the pipeline behaves when the question does not make physical sense for the object (e.g. "what is the spectral type of a quasar?").

- **Triggering input:**

  ```python
  QUERY = ("What is the spectral type and parallax of ton 618, and what are the 3 most recent "
           "arXiv papers whose abstracts mention ton 618? Summarize what the papers suggest "
           "about its current evolutionary status.")
  answer_ton618 = await run_agent(QUERY)
  ```

- **Incorrect / ill-defined output:** `query_simbad` returned, with `is_error: False`:

  ```json
  {
    "object_type": "Bla",
    "spectral_type": "",
    "parallax_mas": NaN,
    "radial_velocity_km_s": 246448.6042633452
  }
  ```

  - `spectral_type` is an empty string, with no explanation of why (a quasar has no stellar spectral type).
  - `parallax_mas` is `NaN`: SIMBAD has no parallax for this object, and `float()` of the masked value gives `NaN`. `NaN` is not even valid JSON.
  - `radial_velocity_km_s` ≈ 246,449 km/s (≈ 0.82 c) is not a stellar radial velocity: it is the cosmological recession velocity derived from the redshift (z ≈ 2.2), but the tool labels it as if it were a star's.
  - The server log (`server_stderr.log`) shows the warning `UserWarning: Warning: converting a masked element to nan.`, which never reaches the LLM.
  - `search_arxiv` returned only **1** paper even though 3 were requested, since few abstracts mention "ton 618".

- **Recovery:** the agentic loop recovered on its own, in 2 turns (≈ US$0.01). The LLM correctly interpreted the `NaN` ("expected for an object this distant") and the velocity ("a cosmological redshift of roughly z ≈ 2.2, not a real stellar velocity"), said that only one paper was found, and explicitly separated what came from the retrieved abstract from its own general knowledge. This was thanks to the model, not to the tool: a less careful model could have reported the `NaN` or the 0.82 c velocity as real stellar values.

- **Production fix:** have `query_simbad` convert masked SIMBAD values to `null` with an explicit note (e.g. `"parallax_mas": null, "note": "parallax not available in SIMBAD"`) and report the redshift instead of a radial velocity for extragalactic objects.

## 3. Extra: long run with no visible output

- **Triggering input:** the same TON 618 query as in failure 2, in an earlier run with the first version of `run_agent`. That version printed nothing until the MCP connection was established and had no limit on the number of LLM calls (`while True:`).

- **Output produced:** none. After ~3 minutes the cell output was still completely blank. I thought the LLM had entered an infinite loop trying to answer a nonsensical question and might be spending the API credit, so I killed the kernel.

  Since not even the first line (`Tools: [...]`), which is printed right after connecting to the server, had appeared, the run most likely stalled while starting or connecting to the MCP server, before any LLM call was made. The root cause could not be confirmed: the server's error messages were not being saved, and the problem did not happen again in later runs.

- **Recovery:** manual intervention (kernel killed).

- **Changes implemented:** I modified `run_agent` so that it shows what is happening at every step and cannot run indefinitely. The key changes were:

  ```python
  print("Starting MCP server...", flush=True)                               # shows the connection step
  async with stdio_client(params, errlog=open("server_stderr.log", "w"))   # saves the server's errors to a file
  ...
  client = anthropic.Anthropic(api_key=..., timeout=60, max_retries=1)     # at most ~1 min per LLM call
  ...
  for turn in range(1, MAX_TURNS + 1):                                     # MAX_TURNS = 5 instead of `while True:`
      ...
      print(f"--- Turn {turn} | {seconds}s | in=... out=... | accumulated ≈ $... ---")  # time and cost per turn
  ```

  It also prints the model's summarized reasoning (`thinking={"type": "adaptive", "display": "summarized"}`) and uses `output_config={"effort": "low"}` to reduce cost while experimenting.

- **Production fix:** cap the number of agent turns and set timeouts on both the MCP connection and the LLM calls, logging every step (and the server's stderr) so a stalled run can be diagnosed instead of just killed.
