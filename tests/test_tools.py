"""
Tests for the three FitFindr tools.

Run from the repo root with:
    python -m pytest tests/

Use `python -m pytest` (not bare `pytest`) so the repo root is on the import
path and `from tools import ...` resolves.

search_listings is deterministic and needs no API key. The suggest_outfit and
create_fit_card tests mock the Groq call (tools._chat), so the whole suite runs
offline. Live LLM behaviour was verified manually during Milestone 3.
"""

import tools
from tools import search_listings, suggest_outfit, create_fit_card, _score_listing, _tokenize
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

TEE = {
    "id": "lst_006", "title": "Graphic Tee — 2003 Tour Bootleg Style",
    "category": "tops", "style_tags": ["graphic tee", "vintage"],
    "colors": ["black"], "size": "L", "price": 24.0, "platform": "depop",
    "description": "Vintage-style bootleg tee with faded graphic.",
}


# ── search_listings ──────────────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0


def test_search_no_results_returns_message_not_exception():
    result = search_listings("designer ballgown", size="XXS", max_price=5)
    assert isinstance(result, str)                 # message, no exception
    assert result.startswith("No listings matched 'designer ballgown'")
    assert "size XXS" in result and "$5.00" in result


def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=40)
    assert isinstance(results, list) and results
    assert all(item["price"] <= 40 for item in results)


def test_search_size_filter_excludes_other_sizes():
    results = search_listings("vintage", size="M")
    assert results
    assert all("m" in item["size"].lower().replace("/", " ").split() for item in results)


def test_search_returns_unmodified_listing_dicts():
    results = search_listings("vintage graphic tee", max_price=30)
    expected_keys = {"id", "title", "description", "category", "style_tags",
                     "size", "condition", "price", "colors", "brand", "platform"}
    assert expected_keys <= set(results[0].keys())


def test_vintage_graphic_tee_under_30_ranks_bootleg_tee_first():
    results = search_listings("vintage graphic tee", max_price=30)
    assert results, "expected at least one match"
    assert results[0]["id"] == "lst_006"
    assert _score_listing(results[0], _tokenize("vintage graphic tee")) == 16
    assert all(r["price"] <= 30 for r in results)


def test_black_combat_boots_size_8_returns_message():
    result = search_listings("black combat boots", size="8")
    assert isinstance(result, str)
    assert "No listings matched 'black combat boots' in size 8" in result


def test_no_results_message_omits_unused_filters():
    result = search_listings("designer ballgown")
    assert result.startswith("No listings matched 'designer ballgown'.")
    assert "$" not in result


def test_results_sorted_by_score_then_price():
    keywords = _tokenize("vintage")
    results = search_listings("vintage", max_price=20)
    keys = [(_score_listing(r, keywords), r["price"]) for r in results]
    assert keys == sorted(keys, key=lambda t: (-t[0], t[1]))


def test_size_token_matching():
    sizes_m = {r["size"] for r in search_listings("vintage", size="m")}
    assert sizes_m == {"M", "M/L", "S/M"}
    assert {r["size"] for r in search_listings("sneakers", size="8")} == {"US 8"}
    assert {r["size"] for r in search_listings("boots", size="US 8.5")} == {"US 8.5"}


def test_empty_or_stopword_description_returns_message():
    for bad in ("", "   ", "something for me"):
        result = search_listings(bad)
        assert isinstance(result, str)
        assert result.startswith("No search terms found")


def test_zero_score_listings_are_dropped():
    keywords = _tokenize("cargo")
    for r in search_listings("cargo"):
        assert _score_listing(r, keywords) > 0


# ── suggest_outfit (LLM mocked — no API key needed) ─────────────────────────

def _boom(*_, **__):
    raise RuntimeError("simulated Groq outage")


def test_suggest_outfit_uses_llm_reply_when_available(monkeypatch):
    monkeypatch.setattr(tools, "_chat", lambda **kw: "Outfit 1: tee + jeans + sneakers.")
    assert suggest_outfit(TEE, get_example_wardrobe()) == "Outfit 1: tee + jeans + sneakers."


def test_suggest_outfit_wardrobe_prompt_names_wardrobe_items(monkeypatch):
    captured = {}
    monkeypatch.setattr(tools, "_chat", lambda **kw: captured.update(kw) or "ok")
    suggest_outfit(TEE, get_example_wardrobe())
    assert "Baggy straight-leg jeans, dark wash" in captured["user"]
    assert "Chunky white sneakers" in captured["user"]
    assert captured["temperature"] == 0.7


def test_suggest_outfit_empty_wardrobe_uses_general_advice_prompt(monkeypatch):
    captured = {}
    monkeypatch.setattr(tools, "_chat", lambda **kw: captured.update(kw) or "ok")
    out = suggest_outfit(TEE, get_empty_wardrobe())
    assert out == "ok"
    assert "general styling advice" in captured["user"]
    assert "Baggy straight-leg jeans" not in captured["user"]


def test_suggest_outfit_handles_missing_items_key(monkeypatch):
    monkeypatch.setattr(tools, "_chat", lambda **kw: "ok")
    assert suggest_outfit(TEE, {}) == "ok"
    assert suggest_outfit(TEE, None) == "ok"


def test_suggest_outfit_api_error_falls_back_to_wardrobe_template(monkeypatch):
    monkeypatch.setattr(tools, "_chat", _boom)
    out = suggest_outfit(TEE, get_example_wardrobe())
    assert out.startswith("[fallback]")
    assert "Baggy straight-leg jeans, dark wash" in out
    assert "Chunky white sneakers" in out


def test_suggest_outfit_api_error_empty_wardrobe_falls_back_to_basics(monkeypatch):
    monkeypatch.setattr(tools, "_chat", _boom)
    out = suggest_outfit(TEE, get_empty_wardrobe())
    assert out.startswith("[fallback]")
    assert "basics" in out


def test_suggest_outfit_empty_llm_reply_falls_back(monkeypatch):
    monkeypatch.setattr(tools, "_chat", lambda **kw: "   ")
    out = suggest_outfit(TEE, get_example_wardrobe())
    assert out.startswith("[fallback]")


# ── create_fit_card (LLM mocked — no API key needed) ────────────────────────

OUTFIT = "Outfit 1: tee + baggy jeans + chunky sneakers.\nOutfit 2: tee + denim jacket."


def test_fit_card_empty_outfit_returns_error_without_llm(monkeypatch):
    monkeypatch.setattr(tools, "_chat", _boom)  # would raise if called
    err = "Error: cannot create a fit card without an outfit suggestion."
    assert create_fit_card("", TEE) == err
    assert create_fit_card("   \n", TEE) == err
    assert create_fit_card(None, TEE) == err


def test_fit_card_missing_listing_fields_returns_error(monkeypatch):
    monkeypatch.setattr(tools, "_chat", _boom)
    out = create_fit_card(OUTFIT, {"title": "Some tee"})
    assert out.startswith("Error: listing is missing required fields")


def test_fit_card_prompt_contains_item_and_outfit(monkeypatch):
    captured = {}
    monkeypatch.setattr(tools, "_chat", lambda **kw: captured.update(kw) or "Caption here.")
    out = create_fit_card(OUTFIT, TEE)
    assert out == "Caption here."
    assert TEE["title"] in captured["user"]
    assert "$24.00" in captured["user"]
    assert "depop" in captured["user"]
    assert "chunky sneakers" in captured["user"]
    assert captured["temperature"] >= 0.9


def test_fit_card_strips_surrounding_quotes(monkeypatch):
    monkeypatch.setattr(tools, "_chat", lambda **kw: '"Scored this tee on Depop."')
    assert create_fit_card(OUTFIT, TEE) == "Scored this tee on Depop."


def test_fit_card_api_error_falls_back_to_template(monkeypatch):
    monkeypatch.setattr(tools, "_chat", _boom)
    out = create_fit_card(OUTFIT, TEE)
    assert out.startswith("[fallback]")
    assert TEE["title"] in out and "$24.00" in out and "depop" in out
    assert "Outfit 1: tee + baggy jeans + chunky sneakers." in out


def test_fit_card_empty_llm_reply_falls_back(monkeypatch):
    monkeypatch.setattr(tools, "_chat", lambda **kw: "  ")
    assert create_fit_card(OUTFIT, TEE).startswith("[fallback]")


# ── regressions found while deliberately breaking tools (Milestone 5) ────────

def test_empty_wardrobe_prompt_forbids_asking_the_user(monkeypatch):
    """Regression: the model once replied by asking for a wardrobe list."""
    captured = {}
    monkeypatch.setattr(tools, "_chat", lambda **kw: captured.update(kw) or "ok")
    suggest_outfit(TEE, get_empty_wardrobe())
    assert "Never ask the user" in captured["system"]
    assert "Do not ask me any questions" in captured["user"]
    assert "Only reference wardrobe pieces that are listed" not in captured["system"]


def test_fit_card_fallback_does_not_double_tag(monkeypatch):
    """Regression: outfit fallback + fit card fallback produced two [fallback] tags."""
    monkeypatch.setattr(tools, "_chat", _boom)
    outfit = suggest_outfit(TEE, get_example_wardrobe())      # -> "[fallback] ..."
    card = create_fit_card(outfit, TEE)                        # -> "[fallback] ..."
    assert card.startswith("[fallback]")
    assert card.count("[fallback]") == 1
