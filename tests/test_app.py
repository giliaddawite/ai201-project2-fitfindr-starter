"""
Tests for handle_query() in app.py.

Run from the repo root with:
    python -m pytest tests/

run_agent is stubbed so these run offline and check only how the session
dict is mapped onto the three Gradio output panels.
"""

import app
from app import handle_query

TEE = {
    "id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops", "style_tags": ["graphic tee", "vintage"],
    "colors": ["black"], "size": "L", "condition": "good", "price": 24.0,
    "platform": "depop", "brand": None,
    "description": "Vintage-style bootleg tee with faded graphic.",
}
OTHER = {**TEE, "id": "lst_033", "title": "Vintage Band Tee — Faded Grey", "price": 19.0}


def _session(**overrides):
    base = {
        "query": "q", "parsed": {}, "search_results": [TEE, OTHER],
        "selected_item": TEE, "wardrobe": {"items": []},
        "outfit_suggestion": "Outfit 1: tee + jeans.", "fit_card": "Caption.", "error": None,
    }
    return {**base, **overrides}


def test_empty_query_returns_prompt_without_running_agent(monkeypatch):
    def boom(*_):
        raise AssertionError("run_agent should not be called")
    monkeypatch.setattr(app, "run_agent", boom)
    a, b, c = handle_query("   ", "Example wardrobe")
    assert "describe what you're looking for" in a
    assert b == "" and c == ""


def test_wardrobe_choice_maps_to_the_right_wardrobe(monkeypatch):
    seen = {}
    monkeypatch.setattr(app, "run_agent", lambda q, w: seen.update(q=q, w=w) or _session())
    handle_query("vintage tee", "Empty wardrobe (new user)")
    assert seen["w"]["items"] == []
    handle_query("vintage tee", "Example wardrobe")
    assert len(seen["w"]["items"]) == 10
    assert seen["q"] == "vintage tee"


def test_error_goes_to_first_panel_only(monkeypatch):
    msg = "No listings matched 'designer ballgown'. Try loosening the size or price filter, or different keywords."
    monkeypatch.setattr(app, "run_agent", lambda q, w: _session(
        error=msg, search_results=[], selected_item=None,
        outfit_suggestion=None, fit_card=None))
    a, b, c = handle_query("designer ballgown", "Example wardrobe")
    assert msg in a
    assert b == "" and c == ""


def test_happy_path_maps_session_to_three_panels(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda q, w: _session())
    a, b, c = handle_query("vintage graphic tee", "Example wardrobe")
    assert "Graphic Tee — 2003 Tour Bootleg Style" in a
    assert "$24.00 on depop" in a
    assert "Size: L" in a and "Condition: good" in a
    assert "Also found 1 other match: Vintage Band Tee — Faded Grey ($19)." in a
    assert b == "Outfit 1: tee + jeans."
    assert c == "Caption."


def test_single_result_has_no_other_matches_line(monkeypatch):
    monkeypatch.setattr(app, "run_agent", lambda q, w: _session(search_results=[TEE]))
    a, _, _ = handle_query("vintage graphic tee", "Example wardrobe")
    assert "Also found" not in a


def test_interface_builds():
    assert app.build_interface() is not None
