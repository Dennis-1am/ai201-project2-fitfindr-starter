# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
- This tool does gathers all the listing that matches the users query.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): the description for a listing i.e. Authentic 90s track jacket with stripe detail down the sleeves. Full zip. Lightweight — great for layering.
- `size` (str): the size of the listed item. Varies between items i.e. clothing may be S / M / L, shoes may be 10/11/12, pants may be W28 etc.
- `max_price` (float): the maximum price of all items that a users query would return. i.e. max_price of $10 all items > $10 will be filtered out or not returned at all.

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
- The result should be a list of individual listing objects. 
- Filtered by max_price & size then reorder by how relevant they are compared to the users query.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if no listings match? -->
- If no listing matches the the users query then we should fail safely and inform the user that they should be more lenient with their searching parameters. (Potential improvement): return a broader range of items i.e. retry query but with the max_price filter turned off.

---

### Tool 2: suggest_outfit

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
- This tool gives the user guidance on potential outfits based on the item they are considering buyiny (new item) and the items in the current wardrobe.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The item that the user is considering to buy.
- `wardrobe` (dict): The current items that the user has in the online wardrobe.

**What it returns:**
<!-- Describe the return value -->
- Should return the LLMs response as a string based on what items the LLM considered to be a potential outfit.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
- If the wardrobe is empty the LLM should inform the user that they should consider adding more items to their wardrobe so that suggestion can be made.

---

### Tool 3: create_fit_card

**What it does:**
<!-- Describe what this tool does in 1–2 sentences -->
This tool generated 2-4 sentence captions for social media or posters based on the listing details.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (str): the potential outfits suggested by the LLMs

**What it returns:**
<!-- Describe the return value -->
- Should return a caption (str) of 2 - 4 sentences.

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
- Inform the user that no captions can be generated because there are no suggested outfits. Which may be due to their wardrobe being empty.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->
N/A

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The planning loop should first query generate a valid query from what the user original query to call the search_listing tool. Then using the returned listing call the suggest_outfit or create_fit_card based on the users full query. If the user wants get outfit suggestions the suggest_outfit is called if the user wants to create captions the create_fit_card is used. The loop will be will exit after all the required task is completed or when MAX_TOOL calls has been reached.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->
The data that is tracked is the return values from these tool calls. Similar to the lab each tool call will have a tool call log then result of the tool call log. These will be stored in some history variable which the LLM will use to generate its final response.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | There are no matching results based on the filter criteria provided. |
| suggest_outfit | Wardrobe is empty | There are no items in the wardrobe to generate outfit suggestions. |
| create_fit_card | Outfit input is missing or incomplete | There are no outfits avaliable that a caption can be generated for. |

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->
![alt text](/User%20Input%20Planning-2026-06-14-184359.png)


---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I plan to use claude to help me generate code based on the plan description. I expect it to produce correct code based on the details in the plan / function descriptions. I will verify it by rereading its generated code and testing it a few times with different queries.

**Milestone 4 — Planning loop and state management:**
I plan to try implementing it myself first then using claude to review my implementation. I'll hightlights the areas of my implementation that I could be wrong or improved then ask claude for suggestions. I expect it to give me some good suggestions or potential bugs it finds. I can verify its output by seeing if the suggestions are applicable most likely it will be.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
<!-- What does the agent do first? Which tool is called? With what input? -->
Parse the users query identify max_price and / or size filters. Calls the search_listing tool with the parsed query. In this case it will be max_price $30, no size filter, and user query i.e. vintage graphic tee / baggy jeans and chunky sneakers.

**Step 2:**
<!-- What happens next? What was returned from step 1? What tool is called now? -->
Generate a outfit or a caption based on what the user wants from the query. The LLM will decide which of these tools are needed based off of the tool description & user query. If either is called we will use the listings returned from step 1 as the input. In this case step 1 will return all listing under $30 that are relevant to vintage graphic tee / baggy jeans and chunky sneakers. The tool that will be called next here is suggest_outfit the user didn't request to generate captions for a outfit so the fit_card tool would not be called.

**Step 3:**
<!-- Continue until the full interaction is complete -->
Repeat step 2 until all task are complete. Tasks completion are also identified by the LLM when it reviews the running responses at the end of each loop iteration. That or the # of tool calls exceeded a certain threshold to be identified at a later time probably something like 20.

By task completion I think the LLM can review the responses at the end of each loop and see if it has all the information needed i.e. the user only request outfit suggestions via the part of the query where they ased for how to style the outfit. So the LLM should know that it doesn't need the fit_card portion of the session result to be filled out. Only the other parts like search result, selected_item, and outfit suggestions to be populated.

**Final output to user:**
<!-- What does the user actually see at the end? -->

The user will see a detailed descriptions of the listings avaliable and the potential outfits that can be created with whats avalaible this will be a string response. Details include price, size, and outfit suggestions.
