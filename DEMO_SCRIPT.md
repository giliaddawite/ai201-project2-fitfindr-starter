# FitFindr — Demo Video Script (~3 minutes)

Before recording: `python app.py` running in a browser tab, a terminal open at the repo root with a large font, and the "Example wardrobe" radio selected.

---

## 1. What it is (0:00–0:20)

**Say:** "FitFindr is a three-tool AI agent for thrifting. You describe what you want in plain English; it searches secondhand listings, styles the best find against your own wardrobe, and writes a shareable caption. The planning loop is in `agent.py`, the tools are in `tools.py`, and every tool result flows through one session dict."

**Show:** the Gradio page with its three empty panels.

## 2. Happy path (0:20–1:10)

**Do:** type `I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers.` and press **Find it**.

**Say while it runs:** "Step one, the query is parsed by regex into a description, size, and max price — `vintage graphic tee`, no size, thirty dollars. Step two, `search_listings` scores all forty listings by keyword overlap and returns the 2003 Tour Bootleg tee first. Step three, that exact listing dict goes into `suggest_outfit` with my ten-item wardrobe. Step four, the outfit text goes into `create_fit_card`."

**Show:** point at each panel. "Panel one is the top listing plus how many other matches there were. Panel two names real pieces from my wardrobe — baggy straight-leg jeans, chunky white sneakers. Panel three is the caption, and notice it reuses the pieces from Outfit 1 — that's the outfit text reaching the last tool, not a caption generated from the listing alone."

## 3. Empty wardrobe (1:10–1:35)

**Do:** switch the radio to **Empty wardrobe (new user)**, run the same query.

**Say:** "Same item, but the wardrobe has no items. `suggest_outfit` doesn't crash and doesn't ask me for a list — it switches to a general-advice prompt and suggests outfits from common basics. The fit card still gets generated."

## 4. Triggered failure: no results (1:35–2:00)

**Do:** click the example **designer ballgown size XXS under $5**.

**Say:** "Now the branch path. Nothing in the dataset matches. `search_listings` returns a message instead of a list — it names the filters that were used and what to try. The loop sees that string, stores it in `session['error']`, and stops. The other two tools never run and no LLM call is made, which is why the other two panels are blank."

## 5. Triggered failures in the terminal (2:00–2:45)

**Do:** in the terminal run `python demo_failures.py` and scroll.

**Say:** "This script breaks every tool on purpose. Section one is the no-results case you just saw, from the agent's side — outfit and fit card are `None`. Section two, empty wardrobe — general advice, no exception. Section three, `create_fit_card` with an empty outfit string returns an error message without ever calling the LLM. Section four sets an invalid Groq key inside this process only — both LLM tools catch the 401 and return `[fallback]` templates, and the agent still completes. My real key isn't touched."

## 6. Tests and wrap-up (2:45–3:00)

**Do:** run `python -m pytest tests/ -q`.

**Say:** "Forty-eight tests cover the parser, the loop's state passing, and every failure mode, with the LLM mocked so they run offline. The tool signatures in the README match `tools.py` exactly, and `planning.md` has the spec, the diagram, and the same walkthrough you just watched."

---

**If a live LLM call is slow on camera:** keep talking through the state flow — the parse result and the selected listing are deterministic, so you can describe them before the outfit panel fills in.
