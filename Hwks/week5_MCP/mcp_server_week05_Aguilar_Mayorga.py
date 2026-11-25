"""Week 5 — MCP server for physics databases (SIMBAD + arXiv)

Exposes two physics database queries as LLM-callable MCP tools. Their JSON
Schemas are generated from the type hints and the Annotated[..., Field(...)]
descriptions, so an LLM can invoke them without additional guidance:

  - query_simbad(object_name): object type, spectral type, parallax and radial
    velocity from SIMBAD (TAP service, through astroquery.simbad).
  - search_arxiv(keyword, max_results): the most recent arXiv papers whose
    abstracts mention the keyword (title, authors, abstract, arXiv ID).

SIMBAD queries go to the Harvard mirror (conf.server = "simbad.harvard.edu")
because the main server in Strasbourg was down (failure mode 1 in
week05_failures_Aguilar_Mayorga.md).

Usage:
    python mcp_server_week05_Aguilar_Mayorga.py --test
        Runs both tools on Betelgeuse without an LLM (no API calls).

    python mcp_server_week05_Aguilar_Mayorga.py
        Serves the tools over stdio. You normally do not run this yourself:
        the MCP client (run_agent in week05_Aguilar_Mayorga.ipynb) launches
        this file as a subprocess and talks to it through stdin/stdout.

Dependencies: pip install -r requirements.txt
"""

import asyncio
import json
import arxiv

from typing import Annotated
from pydantic import Field

from astroquery.simbad import conf
conf.server = "simbad.harvard.edu"  # Use the SIMBAD mirror server when the main one is down


from mcp.server import MCPServer


server = MCPServer("physics-tools")


@server.tool()
async def query_simbad(object_name: Annotated[str, Field(description="Name or identifier of the astronomical " \
                        "object as SIMBAD knows it, e.g. 'Betelgeuse', 'alf Ori', 'HD 39801'.")]) -> dict:
    """Query SIMBAD for basic properties of a named astronomical object.
    Returns a dict with keys: object_type, spectral_type, parallax_mas,
    radial_velocity_km_s.
    Raises ValueError if the object is not found in SIMBAD.
    """
    
    # Extra: Create a new instance of Simbad (zimbad) for each call, 
    # instead of modifying the Simbad class, to avoid accumulating 
    # repeated columns across calls to the server.

    #  This is a workaround for the fact that astroquery.simbad.Simbad is a singleton class.


    from astroquery.simbad import Simbad
    zimbad = Simbad()
    zimbad.add_votable_fields("sp_type", "plx_value", "rvz_radvel", "otype") 
    result_table = zimbad.query_object(object_name)
    if result_table is None or len(result_table) == 0 :
        raise ValueError(f"Object not found in SIMBAD: {object_name}")
    row = result_table[0]
    return {"object_type" : str(row["otype"]),
            "spectral_type" : str(row["sp_type"]),
            "parallax_mas": float(row["plx_value"]),
            "radial_velocity_km_s" : float(row["rvz_radvel"])}


@server.tool()
async def search_arxiv(keyword: Annotated[str, Field(description="Keyword or phrase that must appear in the paper abstract, e.g. 'Betelgeuse'.")],
                        max_results: Annotated[int, Field(ge=1, le=30, description = "How many papers to return, newest first.")] = 5,) -> list:
    """Search arXiv for recent papers matching a keyword.
    Returns a list of dicts, each with keys:
    arxiv_id, title, authors, abstract.
    """
    # implement using the arxiv library


    client = arxiv.Client()
    search = arxiv.Search(
        query=f'abs:"{keyword}"',
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    return [
           {
               "arxiv_id": r.get_short_id(),
               "title": r.title,
               "authors": [a.name for a in r.authors],
               "abstract": r.summary,
           }
           for r in client.results(search)
       ]
    #raise NotImplementedError("Implement search_arxiv using the arxiv library")


async def _test_tools():
    """Quick smoke tests — run before connecting the LLM client."""
    print("--- Testing query_simbad ---")
    result = await query_simbad("Betelgeuse")
    assert "spectral_type" in result, "Missing spectral_type key"
    print(json.dumps(result, indent=2))

    print("\n--- Testing search_arxiv ---")
    results = await search_arxiv("Betelgeuse", max_results=3)
    assert isinstance(results, list) and len(results) > 0, "Expected a non-empty list"
    print(f"{len(results)} result(s). First title: {results[0]['title']}")


async def _serve():
        await server.run_stdio_async()


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        asyncio.run(_test_tools())
    else:
        asyncio.run(_serve())
