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

from tools import search_listings, suggest_outfit, create_fit_card, _get_groq_client
from message import new_message_list, add_user, add_assistant, add_tool_result
import json

_LLM_MODEL = "llama-3.3-70b-versatile"
_CLIENT = _get_groq_client()

MAX_TOOL_CALLS = 3

SYSTEM_PROMPT = (
    "You are a specialized Fashion Advisor Agent. Your primary objective is to help "
    "users find clothing items that match their style, needs, and queries based strictly "
    "on available inventory.\n\n"
    "CORE DIRECTIVE: TOOL GROUNDING (CRITICAL)\n"
    "You are strictly forbidden from recommending items, brands, prices, or fashion "
    "advice that cannot be directly sourced from the data returned by your search tools.\n"
    "1. If a user asks for an item and the tool returns no results, you must explicitly "
    "state that no items were found. Do not invent or hallucinate alternative items.\n"
    "2. Treat the tool output as the absolute and only truth.\n\n"
    "STRICT STEP-BY-STEP RULE:\n"
    "- Only use the exact tools provided to you in the current turn. Do NOT invent, guess, "
    "or hallucinate tool names (such as 'generate_captions' or 'create_caption'). If a tool "
    "is not visible to you, you cannot use it yet.\n\n"
)

# ── standalone tool schemas ──────────────────────────────────────────────────

SEARCH_LISTINGS_TOOL = {
    "type": "function",
    "function": {
        "name": "search_listings",
        "description": (
            "Gathers and returns a list of individual listing objects that match the user's query. "
            "Results are filtered by max_price and size, then ordered by relevance. "
            "If no listings match, fail safely and inform the user that they should be more lenient with their searching parameters."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "The description for a listing (e.g., 'Authentic 90s track jacket with stripe detail down the sleeves. Full zip. Lightweight — great for layering.').",
                },
                "size": {
                    "type": ["string", "null"],
                    "description": "Size string to filter by, or null if no size restriction is specified by the user.",
                },
                "max_price": {
                    "type": ["number", "null"],
                    "description": "The maximum price of all items that a user's query would return, or null if no price limit is specified.",
                }
            },
            "required": ["description"],
        },
    },
}

SUGGEST_OUTFIT_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_outfit",
        "description": (
            "Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits. "
            "Returns a string response containing the suggested outfit. "
            "If the wardrobe is empty, inform the user on what complements the item that they picked out. "
            "Also inform the user they should add items to their online wardrobe to see more personalized suggestions."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "new_item": {
                    "type": "object",
                    "description": (
                        "The full JSON object representing the item the user is considering buying (returned from search_listings). "
                        "CRITICAL: Do NOT just pass the ID string (like 'lst_004'). You MUST pass the "
                        "entire JSON object containing the title, description, price, colors, etc."
                    ),
                },
                "wardrobe": {
                    "type": "object",
                    "description": (
                        "The JSON object representing the user's current wardrobe, containing the 'items' list. "
                        "CRITICAL: Never pass null. If the wardrobe is empty, pass a JSON object "
                        "with an empty list: {\"items\": []}."
                    ),
                }
            },
            "required": ["new_item", "wardrobe"],
        },
    },
}

CREATE_FIT_CARD_TOOL = {
    "type": "function",
    "function": {
        "name": "create_fit_card",
        "description": (
            "Generates 2-4 sentence captions for social media or posters based on the listing details and potential outfits. "
            "Returns the generated caption as a string. "
            "If no outfits are provided (e.g., due to an empty wardrobe), inform the user that no captions can be generated."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "outfit": {
                    "type": "string",
                    "description": "The outfits returned from the suggest_outfit function.",
                },
                "new_item": {
                    "type": "object",
                    "description": (
                        "The full JSON object representing the thrifted item the user is considering buying. "
                        "CRITICAL: Do NOT wrap this object in a string or pass it as a stringified dictionary "
                        "(e.g., do not enclose it in quotes like \"{'item': ...}\"). Pass it as a raw, valid JSON object."
                    ),
                },
            },
            "required": ["outfit", "new_item"],
        },
    },
}


# ── tool dispatch ───────────────────────────────────────────────────────────

def _dispatch(name: str, args: dict, session: dict) -> str:
    print(f"  → Tool call: {name}({args})")
    if name == "search_listings":
        results = search_listings(**args)
        session["search_results"] = results
        session["selected_item"] = results[0] if results else None
        if not results:
            session["error"] = "No listings matched your search. Try relaxing the filters."
        result = results[0]
    if name == "suggest_outfit":
        result = suggest_outfit(session["selected_item"], session["wardrobe"])
        session["outfit_suggestion"] = result
        if not session["wardrobe"].get("items"):
            session["fit_card"] = "No fit card generated — add items to your wardrobe to get a personalized caption."
    elif name == "create_fit_card" and session["wardrobe"]:
        result = create_fit_card(session["outfit_suggestion"], session["selected_item"])
        session["fit_card"] = result
    else:
        result = {"error": f"Unknown tool: {name}"}

    print(f"  ← Result: {json.dumps(result)[:120]}{'...' if len(json.dumps(result)) > 120 else ''}")
    print(f" Session: {session}\n")
    return result


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.
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
    """
    session = _new_session(query, wardrobe)

    # Use LLM to parse user's query the most flexible
    messages = new_message_list(system_prompt=SYSTEM_PROMPT)
    add_user(messages=messages, content=query)
    
    tool_call_count = 0
    while tool_call_count < MAX_TOOL_CALLS:
        
        # 1. DYNAMIC TOOL FILTERING
        # Rule A: search_listings is always available
        available_tools = [SEARCH_LISTINGS_TOOL]
        
        # Rule B: Only allow suggest_outfit if the user explicitly asks for it
        outfit_keywords = ["outfit", "suggest", "wear with", "match", "ideas"]
        if any(word in query.lower() for word in outfit_keywords):
            available_tools.append(SUGGEST_OUTFIT_TOOL)
            
        # Rule C: Only allow create_fit_card if user asks for a caption AND an outfit exists in session
        caption_keywords = ["caption", "fit card", "card", "generate", "write a"]
        user_asked_for_caption = any(word in query.lower() for word in caption_keywords)
        has_suggested_outfit = session.get("outfit_suggestion") is not None
        
        if user_asked_for_caption and has_suggested_outfit:
            available_tools.append(CREATE_FIT_CARD_TOOL)

        # 2. CONSTRUCT API ARGUMENTS DYNAMICALLY
        api_kwargs = {
            "model": _LLM_MODEL,
            "messages": messages,
        }
        
        if available_tools:
            api_kwargs["tools"] = available_tools
            api_kwargs["tool_choice"] = "auto"

        # 3. CALL THE API
        response = _CLIENT.chat.completions.create(**api_kwargs)
        add_assistant(messages=messages, response=response)

        choice = response.choices[0]
        if choice.finish_reason != "tool_calls":
            break  # LLM said it's done — no more tools needed

        for tool_call in choice.message.tool_calls:
            tool_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            result = _dispatch(tool_name, args, session)
            add_tool_result(messages, tool_call.id, json.dumps(result))
            tool_call_count += 1

        if session["fit_card"] is not None or session["error"] is not None:
            break

    return session


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