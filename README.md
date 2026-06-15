# FitFindr — A Tool-Use Planning Agent for Fashion Discovery

FitFindr is an agentic system that helps users find secondhand clothing items and generate outfit ideas based on their existing wardrobe. It demonstrates tool use orchestration, state management, and error handling in an AI agent loop.

**Quick links:** [Tool Inventory](#tool-inventory) | [Planning Loop](#planning-loop-explanation) | [State Management](#state-management) | [Error Handling](#error-handling) | [Spec Reflection](#spec-reflection)

---

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

Run the CLI agent:
```bash
python agent.py
```

Run the Gradio web interface:
```bash
python app.py
```

---

## Tool Inventory

FitFindr uses three interrelated tools, orchestrated through a planning loop that decides which tools to call based on the user's query and the state of prior tool executions.

### Tool 1: `search_listings`

**Purpose:** Find thrifted clothing items matching user criteria from the 40-item mock inventory.

**Inputs:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `description` | `str` | Keywords describing what the user wants (e.g., "vintage graphic tee") |
| `size` | `str \| None` | Size filter; matched case-insensitively within listing sizes (e.g., "M" matches "S/M"). None skips filtering. |
| `max_price` | `float \| None` | Maximum price (inclusive). None skips filtering. |

**Output:** `list[dict]`
- Returns a list of matching listing objects, ranked by relevance (highest match first)
- Each listing contains: `id`, `title`, `description`, `category`, `style_tags` (list), `size`, `condition`, `price` (float), `colors` (list), `brand`, `platform`
- Returns empty list (never raises) if nothing matches

**How it works:**
1. Loads all 40 listings from `data/listings.json`
2. Filters by `max_price` and `size` (if provided)
3. Scores remaining listings by keyword overlap: splits `description` into words and counts how many appear in the listing's title, description, category, style tags, colors, or brand
4. Drops any listing with score 0 (no keyword matches)
5. Sorts by score descending, returns listing objects in order

**Example:**
```python
from tools import search_listings

results = search_listings(
    description="vintage graphic tee",
    size="M",
    max_price=30
)
# Returns: [listing_dict, listing_dict, ...]
# If no matches: []
```

---

### Tool 2: `suggest_outfit`

**Purpose:** Generate outfit pairing suggestions combining a candidate item with pieces from the user's existing wardrobe. Handles empty wardrobes gracefully.

**Inputs:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `new_item` | `dict` | A complete listing object returned from `search_listings()` (not just ID) |
| `wardrobe` | `dict` | A wardrobe object with an `items` key containing a list of wardrobe item dicts. Can be empty. |

**Output:** `str`
- A non-empty text suggestion for outfit combinations
- If wardrobe is empty: returns general styling advice (e.g., "this pairs well with..., try building...")
- If wardrobe has items: returns specific outfit combinations naming pieces from the wardrobe

**How it works:**
1. Extracts key details from `new_item` (title, description, size, colors, price)
2. Checks if `wardrobe['items']` is empty
3. If empty: prompts LLM with general styling context ("what types of pieces pair well with this item?")
4. If not empty: formats wardrobe items and prompts LLM to suggest specific outfit combinations using named wardrobe pieces
5. Returns LLM's text response directly

**Example:**
```python
from tools import suggest_outfit

outfit = suggest_outfit(
    new_item=listing_dict,  # from search_listings
    wardrobe={"items": [{"name": "Black jeans", "category": "bottoms", ...}]}
)
# Returns: "Pair the tee with your black jeans and white sneakers..."
```

---

### Tool 3: `create_fit_card`

**Purpose:** Generate a 2–4 sentence Instagram/TikTok caption for sharing the outfit and thrifted find.

**Inputs:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `outfit` | `str` | The outfit suggestion text returned from `suggest_outfit()` |
| `new_item` | `dict` | The same listing object (used to extract name, price, platform for the caption) |

**Output:** `str`
- A 2–4 sentence caption suitable for social media
- Mentions item name, price, and platform naturally (once each)
- Uses casual, authentic tone (like a real OOTD post, not a product description)
- If outfit is empty/whitespace: returns explanatory error message (does not raise)

**How it works:**
1. Guards against empty or whitespace-only `outfit` string; returns error message if violated
2. Extracts item title, price, and platform from `new_item`
3. Constructs a prompt asking the LLM to write a caption with specific guidelines
4. Calls LLM with `temperature=0.9` for creative variation
5. Returns the caption text

**Example:**
```python
from tools import create_fit_card

caption = create_fit_card(
    outfit="Pair with black jeans and white sneakers...",
    new_item=listing_dict
)
# Returns: "found this gem for $15 on depop and it's already my favorite piece..."
```

---

## Planning Loop Explanation

The planning loop is the core orchestration mechanism in `agent.py`. It decides which tools to call, in what order, based on the user's query and the state of prior executions.

### Loop Flow

```
user query + wardrobe
  ↓
[Initialize session: query, wardrobe, and result slots (all None)]
  ↓
[Add query to message history]
  ↓
(while tool_call_count < MAX_TOOL_CALLS=3)
  ├─ [Decide which tools are available]
  │  ├─ search_listings: ALWAYS available (Rule A)
  │  ├─ suggest_outfit: available if query contains outfit keywords (Rule B)
  │  └─ create_fit_card: available only if user asked for caption AND outfit exists (Rule C)
  │
  ├─ [Call Groq API with dynamic tool list]
  │  └─ LLM decides: use a tool, or stop
  │
  ├─ [If LLM chose a tool: dispatch it]
  │  ├─ tool.search_listings → session["search_results"] and session["selected_item"]
  │  ├─ tool.suggest_outfit → session["outfit_suggestion"]
  │  └─ tool.create_fit_card → session["fit_card"]
  │
  └─ [If LLM said it's done, or fit_card/error exists: break]
  │
  ↓
[Return completed session dict]
```

### Dynamic Tool Filtering (Key Design Choice)

Tools are not all available at once. Availability is determined by:

**Rule A: `search_listings` always available**
- Every query should start by searching for items
- LLM can decide not to use it, but it's an option

**Rule B: `suggest_outfit` gated by keywords**
- Only available if query contains one of: "outfit", "suggest", "wear with", "match", "ideas"
- Prevents accidental outfit suggestions when user only wants to search
- Example: "vintage tee under $30" → no outfit keyword → cannot call suggest_outfit
- Example: "vintage tee that matches my style" → "matches" → suggest_outfit available

**Rule C: `create_fit_card` double-gated**
- Requires user to ask for caption (keywords: "caption", "fit card", "card", "generate", "write a")
- AND requires outfit_suggestion to exist in session already
- Prevents calling create_fit_card when there's no outfit to caption

### Session State Flow

The session dict tracks all intermediate results:

```python
session = {
    "query": "...",                    # Original user query
    "parsed": {},                      # (reserved for future use)
    "search_results": [],              # Results from search_listings
    "selected_item": None,             # Top result (first in search_results)
    "wardrobe": {...},                 # User's wardrobe (input, unchanged)
    "outfit_suggestion": None,         # Result from suggest_outfit
    "fit_card": None,                  # Result from create_fit_card
    "error": None,                     # Set if search_listings returns []
}
```

### Message History

Uses a conversation history pattern (message list) to track the LLM's reasoning:

```python
messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "vintage tee under $30"},
    {"role": "assistant", "content": "...", "tool_calls": [...]},
    {"role": "tool", "tool_call_id": "...", "content": "[listing objects]"},
    # ... more turns until LLM stops
]
```

This allows the LLM to:
- See tool results from prior calls in the same conversation
- Chain multiple tools together (e.g., search → outfit → caption)
- Reason about the results and decide whether more tools are needed

---

## State Management

State is managed through a **session dictionary** (not a class or global state). The session is initialized fresh for each user query and passed through the planning loop.

### Session Initialization

```python
def _new_session(query: str, wardrobe: dict) -> dict:
    return {
        "query": query,              
        "parsed": {},                
        "search_results": [],        
        "selected_item": None,       
        "wardrobe": wardrobe,        
        "outfit_suggestion": None,   
        "fit_card": None,            
        "error": None,               
    }
```

### State Updates During Planning Loop

State is updated by the `_dispatch()` function after each tool call:

```python
if name == "search_listings":
    session["search_results"] = results
    session["selected_item"] = results[0] if results else None
    if not results:
        session["error"] = "No listings matched your search. Try relaxing the filters."

if name == "suggest_outfit":
    session["outfit_suggestion"] = result
    if not session["wardrobe"].get("items"):
        session["fit_card"] = "No fit card generated — add items to your wardrobe..."

if name == "create_fit_card":
    session["fit_card"] = result
```

### Data Flow Through Tools

```
wardrobe (input)
  ↓
[Tool 1: search_listings] → session["selected_item"]
  ↓
[Tool 2: suggest_outfit uses selected_item + wardrobe] → session["outfit_suggestion"]
  ↓
[Tool 3: create_fit_card uses outfit_suggestion + selected_item] → session["fit_card"]
```

### Message History State

Messages list is mutated in-place as the loop progresses:

```python
messages = new_message_list(system_prompt)  # [system]
add_user(messages, query)                   # + [user]
# → LLM response
add_assistant(messages, response)           # + [assistant with tool_calls]
# → tool results
add_tool_result(messages, tool_id, result)  # + [tool]
# ... loop again ...
```

The message list enables the LLM to use tool results as context for the next decision.

---

## Error Handling

Each tool and the planning loop have specific error-handling strategies designed to fail gracefully without raising exceptions.

### Tool 1: `search_listings` — Empty Results

**Scenario:** User searches for "designer ballgown size XXS under $5" (unrealistic constraints).

**Error handling:**
```python
# In search_listings():
if score > 0:
    scored.append((score, listing))
# If nothing matches, scored list is empty
return [listing for _, listing in scored]  # Returns []
```

**In planning loop:**
```python
if name == "search_listings":
    results = search_listings(**args)
    session["search_results"] = results
    session["selected_item"] = results[0] if results else None
    if not results:
        session["error"] = "No listings matched your search. Try relaxing the filters."
```

**User-facing output:**
```
Error: No listings matched your search. Try relaxing the filters.
```

**Why this works:** Returns empty list (not None), loop checks length, sets session error, and breaks. User sees a clear, actionable error.

### Tool 2: `suggest_outfit` — Empty Wardrobe

**Scenario:** User searches with an empty wardrobe and requests outfit suggestions.

**Error handling:**
```python
wardrobe_items = wardrobe.get("items", [])
if not wardrobe_items:
    prompt = (
        f"A user is considering buying this thrifted item:\n{item_summary}\n\n"
        "Their wardrobe is empty. Give general styling advice..."
    )
else:
    # ... use specific wardrobe items ...
```

**Example output:**
```
This vintage tee is perfect for building a minimalist streetwear look. 
Since your wardrobe is empty, I'd recommend pairing it with:
- Black or white basics (jeans, cargo pants)
- A denim or leather jacket for layering
- Minimalist sneakers or boots
```

**Why this works:** Tool doesn't fail; it pivots to general advice, keeping the user journey continuous.

### Tool 3: `create_fit_card` — Missing Outfit

**Scenario:** User requests a fit card but no outfit suggestion exists (e.g., wardrobe was empty and user didn't add items).

**Error handling:**
```python
if not outfit or not outfit.strip():
    return (
        "No caption could be generated because no outfit suggestion is available. "
        "Try adding items to your wardrobe to get outfit suggestions first."
    )
```

**In planning loop:**
```python
elif name == "create_fit_card" and session["wardrobe"]:
    result = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    session["fit_card"] = result
```

**User-facing output:**
```
No caption could be generated because no outfit suggestion is available. 
Try adding items to your wardrobe to get outfit suggestions first.
```

**Why this works:** Checks wardrobe before calling tool, and tool has a second guard for empty outfit. Double safety.

### Planning Loop — Max Tool Calls

**Scenario:** LLM gets stuck in a loop trying to refine results.

**Error handling:**
```python
MAX_TOOL_CALLS = 3
tool_call_count = 0
while tool_call_count < MAX_TOOL_CALLS:
    # ... make tool calls ...
    tool_call_count += 1
```

**Why this works:** Hard cap prevents runaway API calls and costs.

### Planning Loop — Early Exit

**Scenario:** Tool produces a result, and the user doesn't need more.

**Error handling:**
```python
if session["fit_card"] is not None or session["error"] is not None:
    break
```

**Why this works:** Happy path (user got a fit card) and error path (no results) both exit early, avoiding unnecessary tool calls.

### API Error Handling

Groq client errors are **not explicitly caught** — they propagate to the caller. This is intentional:
- Allows the CLI/UI layer to handle API failures (timeouts, quota exceeded, network errors)
- Simplifies tool code (no try/except clutter)
- In a production app, would wrap `run_agent()` call in try/except

---

## Spec Reflection

The implementation meets the specification across five dimensions:

### 1. Three Tools Working Together ✅

All three tools are implemented and integrated:
- **search_listings**: Keyword-based filtering and ranking of 40 mock listings
- **suggest_outfit**: LLM-powered outfit pairing (with empty wardrobe fallback)
- **create_fit_card**: LLM-powered caption generation

Tools are wired into the planning loop and can be chained (search → outfit → caption).

### 2. Planning Loop with Tool Use ✅

The `run_agent()` function implements a multi-turn agentic loop:
- Message history tracks conversation state
- Groq API decides which tools to call (via tool_calls in responses)
- Dynamic tool filtering (Rules A, B, C) ensures tools are used appropriately
- Loop runs until MAX_TOOL_CALLS or user's goal is achieved

**Key design decision:** Tools are not all available at once. Availability is gated by user intent (keywords in query). This prevents the LLM from using tools it shouldn't.

### 3. Session-Based State Management ✅

State flows through a single session dict:
- Initialized fresh per query
- Updated by `_dispatch()` after each tool call
- Passed to the UI layer and returned to the user
- No globals, no side effects outside the session

Intermediate results (search_results, selected_item, outfit_suggestion) are preserved so tools can use them (e.g., create_fit_card uses outfit_suggestion).

### 4. Error Handling Per Tool ✅

Each tool has specific error handling:

| Tool | Error Case | Response | Mechanism |
|------|-----------|----------|-----------|
| search_listings | No results | Return empty list; session sets error message | Check length, set session["error"] |
| suggest_outfit | Empty wardrobe | Return general styling advice | Check wardrobe["items"], use fallback prompt |
| create_fit_card | No outfit | Return explanatory message | Check outfit string, guard before calling |

All errors are returned as strings to the user (not exceptions). This keeps the flow continuous.

### 5. Tool Grounding ✅

System prompt explicitly forbids hallucination:

```
"CORE DIRECTIVE: TOOL GROUNDING (CRITICAL)
You are strictly forbidden from recommending items, brands, prices, or fashion 
advice that cannot be directly sourced from the data returned by your search tools."
```

This is reinforced by:
- Passing full listing objects to tools (not summaries)
- Outfit suggestions reference wardrobe pieces by name
- Captions mention the item's actual price and platform
- LLM's only source of truth is tool output

### 6. Spec Compliance: "Reflection" ✅

The implementation reflects on the spec by:
- Using the exact wardrobe schema from `wardrobe_schema.json`
- Loading listings from the provided `data/listings.json`
- Exposing the three tools in the tool schemas with exact parameter names
- Testing the happy path and no-results path (seen in agent.py main)

---

## Project Structure

```
ai201-project2-fitfindr-starter/
├── agent.py                   # Planning loop + tool orchestration (run_agent, _dispatch)
├── tools.py                   # Three tool implementations
├── app.py                     # Gradio web interface
├── message.py                 # Message history helpers
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + examples
├── utils/
│   └── data_loader.py         # Utilities for loading data
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

---

## Testing

**CLI test (single query):**
```bash
python agent.py
```
Runs two test cases: one happy path and one no-results path.

**Interactive UI:**
```bash
python app.py
```
Open http://localhost:7860 and try the example queries or your own.

**Tool tests (isolated):**
```python
from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe

# Test search
results = search_listings("vintage tee", size="M", max_price=30)
print(f"Found {len(results)} items")

# Test outfit with wardrobe
outfit = suggest_outfit(results[0], get_example_wardrobe())
print(outfit)

# Test caption
caption = create_fit_card(outfit, results[0])
print(caption)
```

## AI USAGE

**General Usage** - Used Gemini & Claude in conjunction to debug and generate code.

**Instance One** - Used Gemini to explain errors from the Groq API i.e. when the API would throw validation errors when attempting to use a function that did not exist. Gemini suggested I update the system prompt to be more strict about what tools are avalaible. So thats what I ended up doing and it fixed it.

**Instance Two** - Used Claude to iterate on the implementation for the agent loop. First I coded it up myself when I got stuck I asked claude for feedback. I also used Gemini to help me think about solutions to prevent the LLM from using tools that it shouldn't be using and it came up with the dynamic tooling solution which I liked. Since it Gemini already came up with the solution I simply asked it to generate the code for it and then refactored some of it before I pushed it out.
