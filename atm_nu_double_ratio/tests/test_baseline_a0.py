"""Tests for the A0 baseline script that need no API call."""

from atmflux.baseline_a0 import REQUESTS, parse_final_json, prompt_for


def test_parse_final_json_takes_the_last_block():
    text = 'draft ```json\n{"R": 0.9}\n``` final ```json\n{"R": 0.61, "expression": "a/b"}\n```'
    obj, problem = parse_final_json(text)
    assert problem is None and obj["R"] == 0.61


def test_parse_final_json_reports_problems():
    assert parse_final_json("no json here")[1] == "no ```json block"
    assert parse_final_json('```json\n{"R": "low"}\n```')[1] == "missing numeric R"


def test_prompts_never_contain_published_values():
    """Layer P must never reach an AI system: no published R in any prompt."""
    for _, lo, hi, w in REQUESTS:
        prompt = prompt_for(lo, hi, w)
        for published in ["0.658", "0.702", "0.60 ", "0.57 ", "Ashie", "Fukuda", "PDG"]:
            assert published not in prompt
