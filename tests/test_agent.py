"""
Tests for the planning loop in agent.py.

Run from the repo root with:
    python -m pytest tests/

_parse_query is pure regex and runs as-is. The run_agent tests replace the
three tools with stubs so they run offline and exercise only the loop's
control flow and state handling.
"""

import agent
from agent import _parse_query, run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

TEE = {
    "id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops", "style_tags": ["graphic tee", "vintage"],
    "colors": ["black"], "size": "L", "price": 24.0, "platform": "depop",
    "description": "Vintage-style bootleg tee with faded graphic.",
}
HOODIE = {**TEE, "id": "lst_015", "title": "Vintage Graphic Hoodie", "price": 26.0}


# ── _parse_query ─────────────────────────────────────────────────────────────

def test_parse_price_under_dollar():
    assert _parse_query("vintage graphic tee under $30") == {
        "description": "vintage graphic tee", "size": None, "max_price": 30.0}


def test_parse_size_m():
    assert _parse_query("90s track jacket size M") == {
        "description": "90s track jacket", "size": "M", "max_price": None}


def test_parse_in_size_8():
    p = _parse_query("black combat boots in size 8")
    assert p["size"] == "8" and p["description"] == "black combat boots"


def test_parse_no_filters():
    assert _parse_query("flowy midi skirt") == {
        "description": "flowy midi skirt", "size": None, "max_price": None}


def test_parse_both_filters_and_filler():
    p = _parse_query("I'm looking for a denim jacket less than 45 dollars in L")
    assert p == {"description": "denim jacket", "size": "L", "max_price": 45.0}


def test_parse_decimal_size_and_price_are_not_sentence_breaks():
    p = _parse_query("chelsea boots size US 8.5 under $50.50")
    assert p == {"description": "chelsea boots", "size": "US 8.5", "max_price": 50.5}


def test_parse_uses_first_sentence_only():
    q = ("I'm looking for a vintage graphic tee under $30. I mostly wear baggy "
         "jeans and chunky sneakers. What's out there?")
    assert _parse_query(q)["description"] == "vintage graphic tee"


def test_parse_empty_query():
    assert _parse_query("") == {"description": "", "size": None, "max_price": None}


# ── run_agent ────────────────────────────────────────────────────────────────

def _stub_tools(monkeypatch, search=None, outfit=None, card=None):
    """Replace the tools imported into agent.py and record their call args."""
    calls = {"search": [], "outfit": [], "card": []}

    def fake_search(description, size=None, max_price=None):
        calls["search"].append((description, size, max_price))
        return search if search is not None else [TEE, HOODIE]

    def fake_outfit(new_item, wardrobe):
        calls["outfit"].append((new_item, wardrobe))
        return outfit if outfit is not None else "Outfit 1: tee + jeans."

    def fake_card(o, new_item):
        calls["card"].append((o, new_item))
        return card if card is not None else "Scored this tee on depop for $24."

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "suggest_outfit", fake_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_card)
    return calls


def test_happy_path_fills_every_session_field(monkeypatch):
    calls = _stub_tools(monkeypatch)
    s = run_agent("vintage graphic tee under $30", get_example_wardrobe())

    assert s["error"] is None
    assert s["query"] == "vintage graphic tee under $30"
    assert s["parsed"] == {"description": "vintage graphic tee", "size": None, "max_price": 30.0}
    assert s["search_results"] == [TEE, HOODIE]
    assert s["selected_item"] == TEE
    assert s["outfit_suggestion"] == "Outfit 1: tee + jeans."
    assert s["fit_card"] == "Scored this tee on depop for $24."


def test_state_flows_from_one_tool_to_the_next(monkeypatch):
    calls = _stub_tools(monkeypatch)
    wardrobe = get_example_wardrobe()
    run_agent("vintage graphic tee under $30", wardrobe)

    assert calls["search"] == [("vintage graphic tee", None, 30.0)]
    assert calls["outfit"] == [(TEE, wardrobe)]              # top result + same wardrobe
    assert calls["card"] == [("Outfit 1: tee + jeans.", TEE)]  # outfit text + same item


def test_no_results_stops_early_and_uses_tool_message(monkeypatch):
    msg = "No listings matched 'designer ballgown' in size XXS under $5.00. Try loosening the size or price filter, or different keywords."
    calls = _stub_tools(monkeypatch, search=msg)
    s = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

    assert s["error"] == msg                     # message comes from the tool verbatim
    assert s["search_results"] == []
    assert s["selected_item"] is None
    assert s["outfit_suggestion"] is None and s["fit_card"] is None
    assert calls["outfit"] == [] and calls["card"] == []   # Tools 2 and 3 never called


def test_empty_wardrobe_is_passed_through_not_rejected(monkeypatch):
    calls = _stub_tools(monkeypatch)
    s = run_agent("vintage tee", get_empty_wardrobe())
    assert s["error"] is None
    assert calls["outfit"][0][1]["items"] == []   # same empty wardrobe reaches Tool 2


def test_fit_card_error_string_is_surfaced_as_session_error(monkeypatch):
    err = "Error: cannot create a fit card without an outfit suggestion."
    _stub_tools(monkeypatch, outfit="", card=err)
    s = run_agent("vintage tee", get_example_wardrobe())
    assert s["fit_card"] == err
    assert s["error"] == err


def test_unexpected_exception_is_caught_not_raised(monkeypatch):
    def boom(*_, **__):
        raise RuntimeError("listings.json is corrupt")
    monkeypatch.setattr(agent, "search_listings", boom)
    s = run_agent("vintage tee", get_example_wardrobe())
    assert s["error"].startswith("Something went wrong")
    assert "listings.json is corrupt" in s["error"]


def test_real_search_no_results_end_to_end(monkeypatch):
    """Real search_listings, stubbed LLM tools: the no-results branch works unmocked."""
    monkeypatch.setattr(agent, "suggest_outfit", lambda *a: "should not run")
    monkeypatch.setattr(agent, "create_fit_card", lambda *a: "should not run")
    s = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
    assert s["error"].startswith("No listings matched 'designer ballgown' in size XXS under $5.00")
    assert s["outfit_suggestion"] is None
