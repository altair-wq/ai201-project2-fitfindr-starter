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
    """
    listings = load_listings()
    
    # 1. Filter by price and size
    filtered_listings = []
    
    def size_matches(query_sz: str, item_sz: str) -> bool:
        q = query_sz.strip().lower()
        it = item_sz.strip().lower()
        if q in it:
            return True
        
        # Check synonyms
        synonyms = {
            "m": ["medium", "med"],
            "s": ["small", "sml"],
            "l": ["large", "lrg"],
            "xl": ["extra large", "x-large", "extra-large"],
            "xs": ["extra small", "x-small"],
            "xxs": ["double extra small", "xx-small"]
        }
        for key, vals in synonyms.items():
            if q == key:
                if any(v in it for v in vals):
                    return True
            if q in vals:
                if key in it or any(v in it for v in vals if v != q):
                    return True
        return False

    for listing in listings:
        # Check price filter
        if max_price is not None:
            price = listing.get("price")
            if price is None or price > max_price:
                continue
                
        # Check size filter
        if size is not None:
            listing_size = listing.get("size")
            if listing_size is None or not size_matches(size, listing_size):
                continue
                
        filtered_listings.append(listing)
        
    # 2. Score each listing by keyword overlap
    import re
    query_words = set(re.findall(r'\b\w+\b', description.lower()))
    if not query_words:
        return []
        
    scored_listings = []
    for listing in filtered_listings:
        text_tokens = []
        if listing.get("title"):
            text_tokens.extend(re.findall(r'\b\w+\b', listing["title"].lower()))
        if listing.get("description"):
            text_tokens.extend(re.findall(r'\b\w+\b', listing["description"].lower()))
        if listing.get("category"):
            text_tokens.extend(re.findall(r'\b\w+\b', listing["category"].lower()))
        if listing.get("brand"):
            text_tokens.extend(re.findall(r'\b\w+\b', listing["brand"].lower()))
        if listing.get("platform"):
            text_tokens.extend(re.findall(r'\b\w+\b', listing["platform"].lower()))
            
        if listing.get("style_tags"):
            for tag in listing["style_tags"]:
                text_tokens.extend(re.findall(r'\b\w+\b', tag.lower()))
        if listing.get("colors"):
            for col in listing["colors"]:
                text_tokens.extend(re.findall(r'\b\w+\b', col.lower()))
                
        listing_words = set(text_tokens)
        overlap = query_words.intersection(listing_words)
        score = len(overlap)
        
        # Only keep listing if score is greater than 0
        if score > 0:
            scored_listings.append((score, listing))
            
    # 3. Sort by score (descending) and return the listing dicts
    scored_listings.sort(key=lambda x: x[0], reverse=True)
    return [listing for _, listing in scored_listings]


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
    """
    if not new_item:
        return "No item provided to suggest an outfit for."
        
    try:
        client = _get_groq_client()
        
        item_title = new_item.get("title", "Unknown Item")
        item_desc = new_item.get("description", "")
        item_price = new_item.get("price", 0.0)
        item_brand = new_item.get("brand") or "unbranded"
        item_colors = ", ".join(new_item.get("colors", []))
        item_tags = ", ".join(new_item.get("style_tags", []))
        
        item_details = (
            f"Item: {item_title}\n"
            f"Brand: {item_brand}\n"
            f"Colors: {item_colors}\n"
            f"Style Tags: {item_tags}\n"
            f"Description: {item_desc}\n"
            f"Price: ${item_price}\n"
        )
        
        wardrobe_items = wardrobe.get("items", []) if isinstance(wardrobe, dict) else []
        
        if not wardrobe_items:
            system_prompt = (
                "You are a professional fashion stylist. A client is considering buying a secondhand item, "
                "but their personal wardrobe details are not available. Provide creative, general styling advice "
                "for this item. Suggest what kinds of items, silhouettes, colors, and styles would pair well with it, "
                "and what overall aesthetic/vibe it suits."
            )
            user_prompt = (
                f"Please suggest outfit styling ideas for this new item:\n\n{item_details}"
            )
        else:
            wardrobe_str = ""
            for idx, item in enumerate(wardrobe_items, 1):
                name = item.get("name", "Unnamed Item")
                cat = item.get("category", "unknown")
                cols = ", ".join(item.get("colors", []))
                tags = ", ".join(item.get("style_tags", []))
                notes = f" ({item.get('notes')})" if item.get("notes") else ""
                wardrobe_str += f"{idx}. {name} [Category: {cat}, Colors: {cols}, Tags: {tags}]{notes}\n"
                
            system_prompt = (
                "You are a professional fashion stylist. A client wants to buy a secondhand item. "
                "Suggest 1-2 complete outfits pairing the new item with pieces from their existing wardrobe. "
                "In your suggestions, explicitly reference named items from their wardrobe. "
                "Include a breakdown of how the pieces work together (colors, styles, layering) to create a cohesive look."
            )
            user_prompt = (
                f"New item to buy:\n{item_details}\n\n"
                f"Client's Wardrobe:\n{wardrobe_str}\n"
                f"Please suggest 1-2 complete outfits using the new item and their wardrobe."
            )
            
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Error suggesting outfit: {str(e)}"


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
    """
    if not outfit or not outfit.strip():
        return "Error: Cannot create a fit card from an empty outfit description."
    if not new_item or not isinstance(new_item, dict):
        return "Error: Invalid new item data provided."
        
    try:
        client = _get_groq_client()
        
        item_title = new_item.get("title", "item")
        item_price = new_item.get("price", 0.0)
        item_platform = new_item.get("platform", "online thrift shop")
        
        system_prompt = (
            "You are a social-media-savvy fashion influencer. Write a short, creative, and shareable "
            "Instagram/TikTok OOTD caption (2-4 sentences) based on the provided outfit suggestion and new thrifted item. "
            "Guidelines:\n"
            "- Tone: casual, authentic, trendy, not corporate or promotional\n"
            "- Mention the item name, price, and platform exactly once each (naturally integrated)\n"
            "- Do NOT output any introductory text (like 'Here is your caption:'), just output the caption itself\n"
            "- Use hashtags and emojis if appropriate to fit the social media style"
        )
        
        user_prompt = (
            f"Item name: {item_title}\n"
            f"Price: ${item_price}\n"
            f"Platform: {item_platform}\n"
            f"Outfit Suggestion:\n{outfit}\n"
        )
        
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.9
        )
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Error generating fit card: {str(e)}"
