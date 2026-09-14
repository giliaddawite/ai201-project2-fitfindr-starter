"""
demo_failures.py — trigger every FitFindr failure mode on purpose, for the demo.

Run from the repo root:
    python demo_failures.py

Each section deliberately breaks one thing and shows that the tool (or the
agent) returns a useful message instead of crashing. Nothing here changes your
.env — the bad-API-key section only overrides the key inside this process.
"""

import os
import sys

sys.stdout.reconfigure(encoding="utf-8")   # Windows console: print em-dashes safely

from tools import search_listings, suggest_outfit, create_fit_card
from agent import run_agent
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe


def banner(n, title):
    print("\n" + "=" * 72)
    print(f" FAILURE {n}: {title}")
    print("=" * 72)


# ── 1. search_listings: nothing matches ──────────────────────────────────────
banner(1, "search_listings — impossible query, no listings match")
print(">>> search_listings('designer ballgown', size='XXS', max_price=5)")
print(search_listings("designer ballgown", size="XXS", max_price=5))

print("\n>>> run_agent('designer ballgown size XXS under $5', example_wardrobe)")
s = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())
print("session['error']    =", s["error"])
print("session['outfit_suggestion'] =", s["outfit_suggestion"])
print("session['fit_card'] =", s["fit_card"])
print("-> agent stopped after search; suggest_outfit / create_fit_card never ran")

# ── 2. suggest_outfit: empty wardrobe ────────────────────────────────────────
banner(2, "suggest_outfit — wardrobe has no items")
tee = search_listings("vintage graphic tee", max_price=30)[0]
print(f">>> suggest_outfit({tee['id']} '{tee['title']}', get_empty_wardrobe())")
out = suggest_outfit(tee, get_empty_wardrobe())
print(out)
print("-> returned general styling advice (no crash, no empty string, no questions back)")

# ── 3. create_fit_card: empty outfit ─────────────────────────────────────────
banner(3, "create_fit_card — empty outfit string")
print(">>> create_fit_card('', tee)")
print(create_fit_card("", tee))
print(">>> create_fit_card('   ', tee)")
print(create_fit_card("   ", tee))
print("-> returned an error message without calling the LLM")

# ── 4. Groq API unavailable (bad key) ────────────────────────────────────────
banner(4, "Groq API failure — invalid API key (this process only)")
os.environ["GROQ_API_KEY"] = "gsk_deliberately_broken_for_demo"
print(">>> suggest_outfit(tee, example_wardrobe)  [with broken key]")
out = suggest_outfit(tee, get_example_wardrobe())
print(out)
print("\n>>> create_fit_card(out, tee)  [with broken key]")
print(create_fit_card(out, tee))
print("\n>>> run_agent('vintage graphic tee under $30', example_wardrobe)  [with broken key]")
s = run_agent("vintage graphic tee under $30", get_example_wardrobe())
print("session['error']    =", s["error"])
print("session['fit_card'] =", s["fit_card"][:90] + "...")
print("-> both LLM tools fell back to templates; the agent still completed")

print("\nDone. Your real GROQ_API_KEY in .env was not modified.")
