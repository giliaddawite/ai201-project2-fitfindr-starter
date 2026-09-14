# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

**macOS / Linux:**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows:**
```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

All three tools live in `tools.py`. Tool 1 is pure Python over the mock dataset; Tools 2 and 3 call the Groq API (model `openai/gpt-oss-120b`, overridable with `GROQ_MODEL` in `.env`). None of them raise on a user-facing failure — each returns a message string instead, so the planning loop in `agent.py` can decide what to do.

### Tool 1 — `search_listings`

```python
def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict] | str
```

| Parameter | Type | Meaning |
|---|---|---|
| `description` | `str` | Free-text keywords, e.g. `"vintage graphic tee"`. Lower-cased, split into words, stopwords dropped. |
| `size` | `str \| None` | Optional size filter. Token-based and case-insensitive: `"M"` matches `"S/M"` and `"M/L"`; `"8"` matches `"US 8"` but not `"US 8.5"` or `"W28"`. |
| `max_price` | `float \| None` | Optional inclusive price ceiling in dollars. |

**Returns:** on success, a `list[dict]` of listing dicts (fields `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`), best match first. Relevance is scored per keyword: +3 for a style-tag hit, +2 for title, +2 for category, +1 for description; zero-score listings are dropped and ties go to the cheaper item. If nothing matches, or the description has no usable keywords, it returns an informative `str` instead (e.g. `"No listings matched 'designer ballgown' in size XXS under $5.00. Try loosening the size or price filter, or different keywords."`). Never returns an empty list, never raises for a no-match.

### Tool 2 — `suggest_outfit`

```python
def suggest_outfit(new_item: dict, wardrobe: dict) -> str
```

| Parameter | Type | Meaning |
|---|---|---|
| `new_item` | `dict` | One listing dict as returned by `search_listings`. |
| `wardrobe` | `dict` | `{"items": [...]}` in the `data/wardrobe_schema.json` format. `items` may be empty or missing. |

**Returns:** a non-empty `str`. With a wardrobe: 1–2 outfits that combine the new item with 2–3 wardrobe pieces named exactly, plus one sentence on why each works (LLM at temperature 0.7). With an empty wardrobe: general styling advice for the item (vibe, pairings, two outfits from common basics) using a separate system prompt that forbids asking the user for more information. If the Groq call fails or returns blank text, it returns a template outfit prefixed with `[fallback]` built from the first complementary wardrobe pieces.

### Tool 3 — `create_fit_card`

```python
def create_fit_card(outfit: str, new_item: dict) -> str
```

| Parameter | Type | Meaning |
|---|---|---|
| `outfit` | `str` | The outfit suggestion text from `suggest_outfit`. |
| `new_item` | `dict` | The same listing dict used for Tool 2 (needs `title`, `price`, `platform`). |

**Returns:** a `str` of 2–4 sentences written like a casual OOTD caption, mentioning the item name, price, and platform once each (LLM at temperature 1.0, so repeated calls differ). If `outfit` is empty, whitespace, or `None` it returns `"Error: cannot create a fit card without an outfit suggestion."` without calling the LLM. If the listing lacks `title`, `price`, or `platform` it returns `"Error: listing is missing required fields (title, price, platform)."`. If the Groq call fails it returns a `[fallback]` template caption built from the item fields.

### Planning loop (not a tool)

`run_agent(query: str, wardrobe: dict) -> dict` in `agent.py` parses the query with regex (`_parse_query`), calls the three tools in order, and returns a session dict with keys `query`, `parsed`, `search_results`, `selected_item`, `wardrobe`, `outfit_suggestion`, `fit_card`, `error`. Tests for everything are in `tests/` — run `python -m pytest tests/` from the repo root (the LLM is mocked, so no key is needed).

---

## Interaction Walkthrough

<!-- Walk through a complete interaction step by step: natural language query → each tool call (and why) → final fit card.
     Walk through this carefully — it's how graders follow your agent's reasoning without a live demo.
     Use a specific example — do not leave this as a template. -->

This is a real run captured from `run_agent()` with the example wardrobe selected (10 items, including "Baggy straight-leg jeans, dark wash" and "Chunky white sneakers"). The LLM outputs below are verbatim from that run; a fresh run will word them differently.

**User query:**

> "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 0 — Parse (no tool, `_parse_query` in `agent.py`):**
The regex parser pulls `under $30` out as the price ceiling and finds no size phrase. Only the first sentence is used for the search description — the second and third sentences describe the wardrobe and ask a styling question, which the wardrobe dict and Tools 2–3 already cover. Filler ("I'm looking for a") is stripped.
Stored as `session["parsed"] = {"description": "vintage graphic tee", "size": None, "max_price": 30.0}`.

**Step 1 — Tool called:**
- Tool: `search_listings`
- Input: `search_listings(description="vintage graphic tee", size=None, max_price=30.0)` — the parsed dict is unpacked straight into the call.
- Why this tool: the user is asking what's out there, and nothing else can happen until we have a concrete listing to style. Search is deterministic and free, so it always runs first.
- Output: a list of 20 listings at or under $30 that scored above zero. The top four, with scores from the +3 / +2 / +2 / +1 rule:

  | id | title | score | price |
  |---|---|---|---|
  | lst_006 | Graphic Tee — 2003 Tour Bootleg Style | 16 | $24 |
  | lst_033 | Vintage Band Tee — Faded Grey | 15 | $19 |
  | lst_002 | Y2K Baby Tee — Butterfly Print | 13 | $18 |
  | lst_015 | Vintage Graphic Hoodie — Faded Black | 12 | $26 |

  Because the result is a list (not a no-results message string), the loop continues. It stores the whole list in `session["search_results"]` and sets `session["selected_item"]` to the first entry, lst_006.

**Step 2 — Tool called:**
- Tool: `suggest_outfit`
- Input: `suggest_outfit(session["selected_item"], session["wardrobe"])` — the exact lst_006 dict from step 1 (verified with an identity check, not a copy) and the wardrobe dict the caller passed in.
- Why this tool: the user asked "how would I style it?" — the tool answers that against the pieces they actually own. The wardrobe has 10 items, so the wardrobe prompt is used (temperature 0.7).
- Output (stored in `session["outfit_suggestion"]`):

  > **Outfit 1** – Graphic Tee — 2003 Tour Bootleg Style + **Baggy straight-leg jeans, dark wash** + **Black combat boots** + **Black crossbody bag**
  > Works because the all-black/indigo palette and boxy-baggy silhouette keep the look gritty and cohesive.
  >
  > **Outfit 2** – Graphic Tee — 2003 Tour Bootleg Style + **Wide-leg khaki trousers** + **Vintage black denim jacket** + **Chunky white sneakers** (+ **Brown leather belt** if you like)
  > The earth-tone trousers contrast the black tee, while the denim jacket echoes the vintage vibe and the white sneakers add street-ready balance.

  Every bolded piece is a real `name` from the example wardrobe.

**Step 3 — Tool called:**
- Tool: `create_fit_card`
- Input: `create_fit_card(session["outfit_suggestion"], session["selected_item"])` — the exact string returned by step 2 and the same lst_006 dict.
- Why this tool: the last step turns the styling into something shareable. The outfit string is non-empty, so the guard passes and the LLM is called at temperature 1.0.
- Output (stored in `session["fit_card"]`):

  > Rocking the Graphic Tee — 2003 Tour Bootleg Style I grabbed for $24.00 on depop, paired with baggy dark-wash jeans and black combat boots for that gritty grunge street vibe. The all-black palette keeps everything cohesive, and the crossbody bag adds a functional edge. Loving how cheap finds can level up a whole look.

  The caption reuses the jeans, boots, and crossbody from Outfit 1 — visible proof that step 2's text reached step 3 rather than the caption being generated from the listing alone.

**Final output to user:**

`session["error"]` is `None`, so `handle_query()` in `app.py` fills all three Gradio panels:

- **🛍️ Top listing found** — "Graphic Tee — 2003 Tour Bootleg Style / $24.00 on depop / Size: L | Condition: good | Brand: no brand listed / Colors: black / Style: graphic tee, vintage, grunge, streetwear, band tee / Vintage-style bootleg tee with faded graphic. Slightly boxy fit. 100% cotton, soft and worn-in. / Also found 19 other matches: Vintage Band Tee — Faded Grey ($19); Y2K Baby Tee — Butterfly Print ($18); Vintage Graphic Hoodie — Faded Black ($26) and 16 more."
- **👗 Outfit idea** — the two outfits from Step 2.
- **✨ Your fit card** — the caption from Step 3.

**The branch path, for contrast.** With the query "designer ballgown size XXS under $5", Step 1 returns the string `"No listings matched 'designer ballgown' in size XXS under $5.00. Try loosening the size or price filter, or different keywords."` instead of a list. The loop copies it into `session["error"]` and returns immediately; Steps 2 and 3 never run, `outfit_suggestion` and `fit_card` stay `None`, and the UI shows the message in the first panel with the other two blank.

---

## Error Handling and Fail Points

<!-- For each tool, describe the specific failure mode and what your agent does in response.
     This maps to the error handling section of the rubric (F5-C1). -->

Every one of these was triggered deliberately during Milestone 5 (see `demo_failures.py`, which reproduces all of them in one run). No path raises an exception to the user.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| `search_listings` | No listing survives the size/price filters, or every keyword scores 0 (e.g. "designer ballgown size XXS under $5") | The tool returns a message string instead of a list: *"No listings matched 'designer ballgown' in size XXS under $5.00. Try loosening the size or price filter, or different keywords."* The message echoes only the filters that were actually used. `run_agent` sees `isinstance(result, str)`, copies the message into `session["error"]`, and returns immediately — `suggest_outfit` and `create_fit_card` never run and no LLM call is made. The UI shows the message in the listing panel and blanks the other two. |
| `search_listings` | Description is empty or only stopwords ("size M under $20", "something for me") | The tool returns *"No search terms found. Tell me what kind of item you're looking for (e.g. 'vintage graphic tee')."* The agent handles it exactly like the no-results case. (`app.py` also catches a fully blank query before the agent runs.) |
| `suggest_outfit` | Wardrobe has no items, or the `items` key is missing, or `wardrobe` is `None` | The tool switches to a second prompt that asks for general styling advice (vibe, pairings, two outfits from common basics) with a system message that forbids asking the user for more information. It returns that text and the agent continues to the fit card. Testing found that the original shared system prompt ("only reference listed pieces") made the model reply by asking for a wardrobe list — the separate prompt fixed it. |
| `suggest_outfit` | Groq API error (bad key, network, rate limit) or a blank reply | The tool catches the exception, logs it, and returns a template outfit prefixed `[fallback]` that pairs the item with the first bottoms and shoes in the wardrobe (or generic basics if the wardrobe is empty). The agent continues; the prefix stays visible so the user knows it isn't LLM output. |
| `create_fit_card` | `outfit` is empty, whitespace, or `None` | Returns *"Error: cannot create a fit card without an outfit suggestion."* without calling the LLM. `run_agent` stores it in `session["fit_card"]` and also copies it into `session["error"]` so the UI surfaces it. |
| `create_fit_card` | Listing is missing `title`, `price`, or `platform` | Returns *"Error: listing is missing required fields (title, price, platform)."* — handled the same way as above. |
| `create_fit_card` | Groq API error or blank reply | Returns a `[fallback]` template caption built from the item's title, price, and platform plus the first line of the outfit (stripping any `[fallback]` tag the outfit already carries so it isn't tagged twice). The agent completes with `error` still `None`. |
| `run_agent` (loop) | Any unexpected exception from a tool (e.g. corrupt `listings.json`) | The whole loop is wrapped in `try/except`; the message lands in `session["error"]` as *"Something went wrong while running the agent: ..."* so Gradio shows a message instead of a traceback. |

---

## Spec Reflection

<!-- Answer both questions with at least 2–3 sentences each. -->

**One way planning.md helped during implementation:**

Writing the relevance-scoring table for `search_listings` before any code (style tag +3, title +2, category +2, description +1, cheaper item wins ties) turned the walkthrough into a test I could actually run. I computed by hand that "vintage graphic tee under $30" should rank lst_006 first with a score of 16, put that in the AI Tool Plan as the verification step, and then the first thing the implementation had to do was reproduce that exact table. It did, which meant the ranking logic was right before any LLM code existed. The same spec made the error-handling table straightforward: each row already said what the tool should *return* on failure, so the planning loop only had to check for those return values rather than invent behaviour on the fly.

**One divergence from your spec, and why:**

The spec originally said `search_listings` returns an empty list `[]` when nothing matches and that the *planning loop* composes the "No listings matched..." message. While testing the no-results path directly from the terminal, I decided I preferred the message to come from the tool itself, so the same informative text appears whether the tool is called on its own or through the agent. The return type became `list[dict] | str`, the loop now checks `isinstance(result, str)` instead of `len(result) == 0`, and planning.md, the docstring, and the tests were all updated to match.

Two smaller divergences surfaced the same way. Size matching was specified as substring-based, but the first test showed "8" matching the waist size "W28" and "US 8.5", so it became whole-token matching. And the course-suggested model, `meta-llama/llama-4-scout-17b-16e-instruct`, turned out to be retired on Groq (404 `model_not_found`), so the code uses `openai/gpt-oss-120b` via a `GROQ_MODEL` constant that can be overridden in `.env`.

---

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
