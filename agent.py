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
    """
    import re

    # 1. Parsing Helper Functions
    def parse_size(q_str: str) -> str | None:
        q = q_str.lower()
        m = re.search(r'\bsize\s*[:\-]?\s*([a-z0-9/\-]+)', q)
        if m:
            val = m.group(1).strip()
            return val.upper() if len(val) <= 3 else val
            
        for size_word in ["double extra small", "extra small", "small", "medium", "large", "extra large", "oversized"]:
            if re.search(r'\b' + re.escape(size_word) + r'\b', q):
                return size_word
                
        for size_abbr in ["xxs", "xs", "s", "m", "l", "xl", "xxl"]:
            if re.search(r'\b' + size_abbr + r'\b', q):
                return size_abbr.upper()
                
        m_waist = re.search(r'\bw(\d{2})\b', q)
        if m_waist:
            return f"W{m_waist.group(1)}"
            
        return None

    def parse_price(q_str: str) -> float | None:
        q = q_str.lower()
        pattern = r'(?:under|below|less\s+than)\s*\$?(\d+(?:\.\d+)?)'
        m = re.search(pattern, q)
        if m:
            return float(m.group(1))
        return None

    def parse_description(q_str: str) -> str:
        q = q_str.strip()
        prefixes = [
            r"^i'm looking for a\s+",
            r"^i'm looking for\s+",
            r"^looking for a\s+",
            r"^looking for\s+",
            r"^find me a\s+",
            r"^find me\s+",
            r"^search for a\s+",
            r"^search for\s+",
            r"^i want a\s+",
            r"^i want\s+"
        ]
        for pref in prefixes:
            q_new = re.sub(pref, "", q, flags=re.IGNORECASE)
            if q_new != q:
                q = q_new
                break
                
        separators = [
            r"\bunder\b",
            r"\bbelow\b",
            r"\bless than\b",
            r"\bsize\b",
            r"\bin size\b",
            r",",
            r"\.",
            r"\bi mostly wear\b",
            r"\bi wear\b",
            r"\bwith\b"
        ]
        
        split_idx = len(q)
        for sep in separators:
            m = re.search(sep, q, flags=re.IGNORECASE)
            if m and m.start() < split_idx:
                split_idx = m.start()
                
        desc = q[:split_idx].strip()
        
        if not desc:
            clean_q = q_str
            clean_q = re.sub(r'(?:under|below|less\s+than)\s*\$?\d+(?:\.\d+)?', '', clean_q, flags=re.IGNORECASE)
            clean_q = re.sub(r'\bsize\s*[:\-]?\s*[a-z0-9/\-]+', '', clean_q, flags=re.IGNORECASE)
            clean_q = re.sub(r'[,.]', ' ', clean_q)
            desc = " ".join(clean_q.split())
            
        return desc

    # Step 1: Initialize the session with _new_session().
    session = _new_session(query, wardrobe)

    # Step 2: Parse parameters and store them.
    desc = parse_description(query)
    size = parse_size(query)
    price = parse_price(query)

    session["description"] = desc
    session["size"] = size
    session["max_price"] = price
    session["parsed"] = {
        "description": desc,
        "size": size,
        "max_price": price
    }

    # Step 3: Call search_listings() with the parsed parameters.
    results = search_listings(desc, size=size, max_price=price)
    session["search_results"] = results

    # Step 4: If no results, stop early.
    if not results:
        session["error"] = "No listings found matching your description. Try loosening your size, price, or description filters."
        return session

    # Step 5: Select the top item.
    session["selected_item"] = results[0]

    # Step 6: Call suggest_outfit().
    outfit_suggestion = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit_suggestion

    if not outfit_suggestion or outfit_suggestion.startswith("Error"):
        session["error"] = "Failed to suggest outfit."
        return session

    # Step 7: Call create_fit_card().
    fit_card = create_fit_card(outfit_suggestion, session["selected_item"])
    session["fit_card"] = fit_card

    if not fit_card or fit_card.startswith("Error"):
        session["error"] = "Failed to generate fit card."
        return session

    # Step 8: Return the session.
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
    print(f"Selected item: {session2['selected_item']}")
    print(f"Outfit suggestion: {session2['outfit_suggestion']}")
    print(f"Fit card: {session2['fit_card']}")
    
    # Confirm requirements for no-results path:
    assert session2["error"] is not None, "Error is not set!"
    assert session2["selected_item"] is None, "Selected item should be None!"
    assert session2["outfit_suggestion"] is None, "Outfit suggestion should be None!"
    assert session2["fit_card"] is None, "Fit card should be None!"
    print("\nAssertions passed: early exit verified successfully.")
