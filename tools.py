"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()
LLM_MODEL = "llama-3.3-70b-versatile"

# ── Groq client ───────────────────────────────────────────────────────────────

_client: Groq | None = None

def _get_groq_client() -> Groq:
    """Initialize and return a shared Groq client using GROQ_API_KEY from .env."""
    global _client
    if _client is None:
        api_key = os.environ.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not set. Add it to a .env file in the project root."
            )
        _client = Groq(api_key=api_key)
    return _client


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
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
        Returns an empty list if nothing matches — does NOT raise an exception.

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
    listings = load_listings()

    # Filter by price and size
    filtered = []
    for listing in listings:
        if max_price is not None and listing["price"] > max_price:
            continue
        if size is not None and size.lower() not in listing["size"].lower():
            continue
        filtered.append(listing)

    # Score by keyword overlap with description
    keywords = set(description.lower().split())
    scored = []
    for listing in filtered:
        searchable = " ".join([
            listing["title"],
            listing["description"],
            listing["category"],
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
            listing.get("brand") or "",
        ]).lower()
        score = sum(1 for kw in keywords if kw in searchable)
        if score > 0: # can adjust to make more accurate
            scored.append((score, listing))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored]


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
    item_summary = (
        f"{new_item.get('title', 'item')} — {new_item.get('description', '')} "
        f"(Size: {new_item.get('size', 'N/A')}, Color(s): {', '.join(new_item.get('colors', []))}, "
        f"${new_item.get('price', '?')})"
    )

    wardrobe_items = wardrobe.get("items", [])
    if not wardrobe_items:
        prompt = (
            f"A user is considering buying this thrifted item:\n{item_summary}\n\n"
            "Their wardrobe is empty. Give general styling advice: what types of pieces "
            "pair well with this item, what aesthetic or vibe it suits, and how to build "
            "an outfit around it. Keep it friendly and specific."
        )
    else:
        wardrobe_text = "\n".join(
            f"- {item.get('name', 'Unknown')} ({item.get('category', '')}): "
            f"{item.get('color', '')} {item.get('brand', '')}".strip()
            for item in wardrobe_items
        )
        prompt = (
            f"A user is considering buying this thrifted item:\n{item_summary}\n\n"
            f"Their current wardrobe includes:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfits using the new item and specific pieces from "
            "the wardrobe. Be specific about which wardrobe items to pair together and why."
        )

    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content


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
    if not outfit or not outfit.strip():
        return (
            "No caption could be generated because no outfit suggestion is available. "
            "Try adding items to your wardrobe to get outfit suggestions first."
        )

    client = _get_groq_client()
    item_name = new_item.get("title", "this find")
    price = new_item.get("price", "?")
    platform = new_item.get("platform", "a thrift platform")

    prompt = (
        f"Write a 2–4 sentence Instagram/TikTok caption for this thrifted outfit.\n\n"
        f"Item: {item_name} — ${price} from {platform}\n"
        f"Outfit: {outfit}\n\n"
        "Guidelines:\n"
        "- Sound casual and authentic like a real OOTD post, not a product description\n"
        "- Mention the item name, price, and platform naturally (once each)\n"
        "- Capture the outfit vibe in specific, vivid terms\n"
        "- Keep it 2–4 sentences total\n"
        "Output only the caption text, nothing else."
    )

    response = client.chat.completions.create(
        model=_LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
    )
    return response.choices[0].message.content
