"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    # Step 1: fresh session — the single source of truth for this run.
    session = _new_session(query, wardrobe)

    try:
        # Step 2: parse the natural-language query into tool arguments.
        session["parsed"] = _parse_query(query)

        # Step 3: search. The tool returns a message string (not a list) when
        # nothing matches — that string is the error, and the run stops here.
        result = search_listings(**session["parsed"])
        if isinstance(result, str):
            session["error"] = result
            return session
        session["search_results"] = result

        # Step 4: pick the best match (highest score, cheapest on ties).
        session["selected_item"] = result[0]

        # Step 5: outfit ideas. The tool handles the empty-wardrobe case itself.
        session["outfit_suggestion"] = suggest_outfit(
            session["selected_item"], session["wardrobe"]
        )

        # Step 6: shareable caption. The tool returns an "Error: ..." string
        # rather than raising if the outfit is missing; surface that as the
        # session error so the UI can show it.
        session["fit_card"] = create_fit_card(
            session["outfit_suggestion"], session["selected_item"]
        )
        if session["fit_card"].startswith("Error:"):
            session["error"] = session["fit_card"]

    except Exception as exc:  # last line of defence — never leak a traceback
        session["error"] = f"Something went wrong while running the agent: {exc}"

    # Step 7: hand the completed session back to the caller.
    return session


# ── query parsing ─────────────────────────────────────────────────────────────

# "under $30", "below 30", "less than $30", "max 30", "< 30", "$30 max"
_PRICE_RE = re.compile(
    r"(?:\b(?:under|below|less than|max(?:imum)?|up to|<)\s*\$?\s*(\d+(?:\.\d+)?)"
    r"|\$\s*(\d+(?:\.\d+)?))\b(?:\s*(?:dollars|bucks|usd))?(?:\s*(?:max|or less|tops))?",
    re.IGNORECASE,
)
# "size M", "size 8", "size US 8.5", "size W30", "in size M", "size XL (oversized)"
_SIZE_RE = re.compile(
    r"\bsize\s+((?:us\s+)?[a-z0-9./]+(?:\s*\((?:oversized|fits oversized|adjustable)\))?)",
    re.IGNORECASE,
)
# "in M", "in an XL" — only for the standard letter sizes, so "in blue" is left alone
_SIZE_IN_RE = re.compile(r"\bin\s+(?:an?\s+)?(xxs|xs|s|m|l|xl|xxl)\b", re.IGNORECASE)

# Phrases that describe intent, not the item. Removed before searching.
_FILLER_RE = re.compile(
    r"\b(?:i'?m looking for|i am looking for|looking for|i'?m after|i want|i need|"
    r"i'?d like|find me|show me|search for|do you have|is there|something like|"
    r"something|anything|please|hey|hi)\b",
    re.IGNORECASE,
)


def _parse_query(query: str) -> dict:
    """
    Extract search arguments from a natural-language request using regex.

    Returns a dict with exactly the keyword arguments search_listings takes:
        {"description": str, "size": str | None, "max_price": float | None}

    Rules (see planning.md → Planning Loop → Query parsing choice):
      * price  — "under $30", "below 30", "less than 30", "max 30", "$30"
      * size   — "size M", "size US 8.5", "in M"
      * description — the FIRST sentence of the query with the matched price
        and size phrases and filler ("looking for", "I want", ...) removed.
        Later sentences usually describe the user's wardrobe or ask a styling
        question, which the wardrobe dict and later tools already cover.
    """
    text = query or ""

    max_price: float | None = None
    m = _PRICE_RE.search(text)
    if m:
        max_price = float(m.group(1) or m.group(2))
        text = text[: m.start()] + " " + text[m.end():]

    size: str | None = None
    m = _SIZE_RE.search(text) or _SIZE_IN_RE.search(text)
    if m:
        size = m.group(1).strip()
        text = text[: m.start()] + " " + text[m.end():]

    # First sentence only (price/size were removed above, so "8.5" / "$30.50"
    # can no longer be mistaken for a sentence break).
    first_sentence = re.split(r"[.!?]", text, maxsplit=1)[0]
    description = _clean(first_sentence)
    if not description:
        # Nothing survived in the first sentence — fall back to the whole query
        # so unusual phrasings still produce some keywords for the search.
        description = _clean(text)

    return {"description": description, "size": size, "max_price": max_price}


def _clean(text: str) -> str:
    """Strip filler phrases, dangling punctuation, and extra whitespace."""
    text = _FILLER_RE.sub(" ", text)
    text = re.sub(r"[,;:()\"]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip(" -")
    # Drop articles/prepositions left dangling at either end after removals.
    return re.sub(
        r"^(?:(?:a|an|the|in|for|with)\s+)+|(?:\s+(?:a|an|the|in|for|with))+$",
        "", text, flags=re.IGNORECASE,
    )


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
