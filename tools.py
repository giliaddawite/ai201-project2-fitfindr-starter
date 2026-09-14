"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict] | str
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict] | str:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        If nothing matches (or the description has no usable keywords), returns
        an informative message string instead, e.g.
        "No listings matched 'designer ballgown' in size XXS under $5.00. ..."
        Never returns an empty list and never raises for a no-match condition.
        Callers should check `isinstance(result, str)` before using the results.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    keywords = _tokenize(description)
    if not keywords:
        return (
            "No search terms found. Tell me what kind of item you're looking "
            "for (e.g. 'vintage graphic tee')."
        )

    size_tokens = _size_tokens(size)

    scored: list[tuple[int, float, dict]] = []
    for listing in load_listings():
        # --- hard filters -------------------------------------------------
        if max_price is not None and listing["price"] > max_price:
            continue
        if size_tokens and not size_tokens <= _size_tokens(listing["size"]):
            continue

        # --- relevance score ---------------------------------------------
        score = _score_listing(listing, keywords)
        if score > 0:
            scored.append((score, listing["price"], listing))

    if not scored:
        return _no_results_message(description, size, max_price)

    # Highest score first; cheaper item wins ties.
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [listing for _, _, listing in scored]


def _no_results_message(description: str, size: str | None, max_price: float | None) -> str:
    """Build the human-readable 'nothing matched' message, echoing the filters used."""
    msg = f"No listings matched '{description.strip()}'"
    if size:
        msg += f" in size {size}"
    if max_price is not None:
        msg += f" under ${max_price:.2f}"
    return msg + ". Try loosening the size or price filter, or different keywords."


# Words that carry no search signal on their own.
_STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "for", "with", "some", "to",
    "i", "im", "i'm", "me", "my", "is", "it", "that", "this", "on", "at",
    "want", "need", "looking", "find", "something", "please", "any",
}

# Points awarded when a keyword appears in each listing field (see planning.md).
_STYLE_TAG_POINTS = 3
_TITLE_POINTS = 2
_CATEGORY_POINTS = 2
_DESCRIPTION_POINTS = 1


def _tokenize(text: str | None) -> list[str]:
    """Lower-case `text`, split into words, and drop stopwords and empties."""
    if not text:
        return []
    words = re.findall(r"[a-z0-9']+", text.lower())
    return [w for w in words if w not in _STOPWORDS]


def _size_tokens(size: str | None) -> set[str]:
    """
    Split a size string into comparable whole tokens, e.g.
    "S/M" -> {"s", "m"}, "US 8.5" -> {"us", "8.5"}, "XL (oversized)" -> {"xl", "oversized"}.
    A requested size matches a listing when every requested token appears in
    the listing's tokens, so "M" matches "S/M" but "8" does not match "W28" or "8.5".
    """
    if not size:
        return set()
    return set(re.findall(r"[a-z0-9.]+", size.lower()))


def _score_listing(listing: dict, keywords: list[str]) -> int:
    """
    Sum relevance points for every keyword, using case-insensitive substring
    matching against style_tags, title, category, and description.
    """
    tags = [t.lower() for t in listing.get("style_tags", [])]
    title = listing.get("title", "").lower()
    category = listing.get("category", "").lower()
    desc = listing.get("description", "").lower()

    score = 0
    for kw in keywords:
        if any(kw in tag for tag in tags):
            score += _STYLE_TAG_POINTS
        if kw in title:
            score += _TITLE_POINTS
        if kw in category:
            score += _CATEGORY_POINTS
        if kw in desc:
            score += _DESCRIPTION_POINTS
    return score


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    items = (wardrobe or {}).get("items") or []
    item_spec = _format_listing(new_item)

    if items:
        wardrobe_lines = "\n".join(_format_wardrobe_item(w) for w in items)
        system_prompt = (
            "You are a thrift-savvy personal stylist. Only reference wardrobe "
            "pieces that are listed. Be specific and concise."
        )
        user_prompt = (
            f"I'm thinking about buying this thrifted piece:\n{item_spec}\n\n"
            f"Here is everything already in my wardrobe:\n{wardrobe_lines}\n\n"
            "Suggest 1-2 complete outfits that combine the new piece with 2-3 "
            "pieces from my wardrobe. Refer to wardrobe pieces by their exact "
            "names. For each outfit, add one sentence on why it works (color, "
            "silhouette, or shared style). Keep the whole answer under 150 words."
        )
    else:
        # No wardrobe: a different system prompt, because "only reference listed
        # pieces" would make the model ask the user for a list instead of helping.
        system_prompt = (
            "You are a thrift-savvy personal stylist. The user has not shared a "
            "wardrobe, so give general styling advice using common basics. Never "
            "ask the user for more information. Be specific and concise."
        )
        user_prompt = (
            f"I'm thinking about buying this thrifted piece:\n{item_spec}\n\n"
            "I don't have a wardrobe on file. Give general styling advice: what "
            "kinds of pieces pair well with it, what vibe it suits, and 2 example "
            "outfits built from common basics (jeans, tees, sneakers, jackets, "
            "etc.). Do not ask me any questions. Keep it under 150 words."
        )

    try:
        text = _chat(
            system=system_prompt,
            user=user_prompt,
            temperature=0.7,
        )
        if text and text.strip():
            return text.strip()
    except Exception as exc:  # network, auth, rate limit, etc.
        print(f"[suggest_outfit] LLM call failed: {exc}")

    return _fallback_outfit(new_item, items)


# ── LLM helpers ───────────────────────────────────────────────────────────────

# The course spec named meta-llama/llama-4-scout-17b-16e-instruct, but Groq has
# retired it (404 model_not_found). Override with GROQ_MODEL in .env if needed.
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b")


def _chat(system: str, user: str, temperature: float) -> str:
    """Send one system+user exchange to Groq and return the stripped reply."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


def _format_listing(item: dict) -> str:
    """One-paragraph spec of a listing for use inside a prompt."""
    return (
        f"- Title: {item.get('title', 'Unknown item')}\n"
        f"- Category: {item.get('category', 'unknown')}\n"
        f"- Colors: {', '.join(item.get('colors', [])) or 'unknown'}\n"
        f"- Style tags: {', '.join(item.get('style_tags', [])) or 'none'}\n"
        f"- Size: {item.get('size', 'unknown')}\n"
        f"- Description: {item.get('description', '')}"
    )


def _format_wardrobe_item(w: dict) -> str:
    """Single bullet for a wardrobe item: name (category, colors, tags, notes)."""
    parts = [
        w.get("category", "unknown"),
        ", ".join(w.get("colors", [])) or "no color listed",
        ", ".join(w.get("style_tags", [])) or "no tags",
    ]
    if w.get("notes"):
        parts.append(w["notes"])
    return f"- {w.get('name', 'unnamed item')} ({'; '.join(parts)})"


def _fallback_outfit(new_item: dict, items: list[dict]) -> str:
    """
    Template outfit used when the LLM is unavailable. Pairs the new item with
    the first wardrobe piece from each complementary category, or with generic
    basics when the wardrobe is empty.
    """
    title = new_item.get("title", "this piece")
    category = new_item.get("category", "")
    wanted = [c for c in ("tops", "bottoms", "shoes", "outerwear") if c != category][:2]

    picks = []
    for cat in wanted:
        match = next((w for w in items if w.get("category") == cat), None)
        if match:
            picks.append(match.get("name", cat))

    if picks:
        return (
            f"[fallback] Pair the {title} with your {' and your '.join(picks)} "
            "for an easy everyday look."
        )
    return (
        f"[fallback] Pair the {title} with neutral basics — straight-leg jeans, "
        "a plain tee or tank, and clean sneakers — and let the thrifted piece "
        "be the focal point."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # --- guards -----------------------------------------------------------
    if not outfit or not str(outfit).strip():
        return "Error: cannot create a fit card without an outfit suggestion."

    new_item = new_item or {}
    missing = [k for k in ("title", "price", "platform") if not new_item.get(k)]
    if missing:
        return "Error: listing is missing required fields (title, price, platform)."

    title = new_item["title"]
    price = new_item["price"]
    platform = new_item["platform"]

    # --- prompt -----------------------------------------------------------
    user_prompt = (
        f"The thrifted piece: {title}\n"
        f"Price: ${price:.2f}\n"
        f"Platform: {platform}\n"
        f"Colors: {', '.join(new_item.get('colors', [])) or 'unknown'}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', [])) or 'none'}\n\n"
        f"How it's being styled:\n{outfit.strip()}\n\n"
        "Write a 2-4 sentence caption for an Instagram or TikTok outfit post. "
        "Rules: sound like a real person sharing their OOTD, not a product "
        "listing. Mention the item name, the price, and the platform naturally, "
        "each exactly once. Name the vibe in specific terms. No hashtags, no "
        "emojis, no bullet points, no quotation marks around the caption."
    )

    # --- LLM call with fallback ------------------------------------------
    try:
        text = _chat(
            system=(
                "You write short, casual, authentic social captions for "
                "secondhand fashion finds. Plain prose only."
            ),
            user=user_prompt,
            temperature=FIT_CARD_TEMPERATURE,
        )
        text = text.strip().strip('"“”').strip()
        if text:
            return text
    except Exception as exc:  # network, auth, rate limit, etc.
        print(f"[create_fit_card] LLM call failed: {exc}")

    first_line = outfit.strip().splitlines()[0].strip()
    first_line = re.sub(r"^\[fallback\]\s*", "", first_line)  # don't double-tag
    return (
        f"[fallback] Thrifted this {title} on {platform} for ${price:.2f} and "
        f"it's already on repeat. {first_line}"
    )


# Higher than suggest_outfit so repeated captions for the same input differ.
FIT_CARD_TEMPERATURE = 1.0
