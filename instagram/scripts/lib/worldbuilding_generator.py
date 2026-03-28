"""
Worldbuilding generator — produces unique planetary exploration lore from ceramic vision data.

Two-phase generation:
  Phase 1: Single AI call generates ALL formation_history lines at once → ensures diversity
  Phase 2: Per-piece AI call generates the remaining 4 fields (surface_geology, orbital_data,
           inhabitants, generated_caption) with the lore line as context
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

# Load .env before any other imports that need env vars
from dotenv import load_dotenv
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

# Ensure project root is on sys.path for caption_generator imports
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from openai import OpenAI
from caption_generator import get_ai_config
from geology_vocabulary import (
    build_vocabulary_block, check_banned_words,
    BANNED_FOOD_WORDS, BANNED_FABRIC_WORDS,
)


def _clean(text):
    """Replace underscores in color/surface names for readability."""
    replacements = {
        "slate_blue": "slate blue", "chun_blue": "deep blue", "seafoam": "seafoam green",
        "oxblood": "oxblood red", "earth_tones": "earth tones", "ice_blue": "ice blue",
        "dark_blue": "dark blue", "carbon_trapping": "carbon-trapped",
        "color_pooling": "color-pooled", "iron_speckling": "iron-speckled",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.replace("_", " ")


def _fmt_list(items, max_items=6):
    """Format a JSON list or python list into a comma-separated string."""
    if isinstance(items, str):
        try:
            items = json.loads(items)
        except (json.JSONDecodeError, TypeError):
            return items or "unknown"
    if not items:
        return "unknown"
    return ", ".join(str(_clean(i)) for i in items[:max_items])


def _get_client():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    return OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1"), get_ai_config()


def _parse_json_response(raw):
    """Strip markdown fences and parse JSON."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    if raw.startswith("json"):
        raw = raw[4:]
    return json.loads(raw.strip())


# --- STOP WORDS: words that appeared too often in previous batch ---
# We track these dynamically and ban them if they appear 3+ times across the set
_BANNED_OVERFLOW = {"watched", "weep", "weeping", "pool", "pooling", "cool", "cooling", "bled", "bleed", "stain"}


_MAX_LORE_RETRIES = 3
_MAX_WB_RETRIES = 2


def generate_all_lore(pieces_vision, _retry_count=0):
    """
    Generate formation_history for ALL pieces in one AI call.

    Args:
        pieces_vision: list of dicts, each with keys:
            planet_name, colors, textures, mood, description, hypotheses
        _retry_count: internal counter for retry limiting

    Returns:
        dict mapping planet_name -> lore string
    """
    client, config = _get_client()

    # Build vocabulary blocks for each planet
    planet_briefs = []
    for pv in pieces_vision:
        # Parse color/surface lists from the brief format
        colors_raw = pv.get('colors', 'unknown')
        textures_raw = pv.get('textures', 'unknown')
        colors_list = [c.strip() for c in str(colors_raw).split(',') if c.strip() and c.strip() != 'unknown']
        surfaces_list = [s.strip() for s in str(textures_raw).split(',') if s.strip() and s.strip() != 'unknown']
        mood_raw = pv.get('mood', '')

        vocab_block = build_vocabulary_block(colors_list, surfaces_list, mood_raw)

        brief = (
            f"- {pv['planet_name']}: "
            f"colors: {pv['colors']}, "
            f"textures: {pv['textures']}, "
            f"mood: {pv['mood']}, "
            f"form: {pv['form']}"
        )
        if pv.get('description'):
            brief += f", surface: {pv['description'][:100]}"
        if pv.get('hypotheses'):
            brief += f", notes: {pv['hypotheses'][:120]}"
        if vocab_block:
            brief += f"\n  GEOLOGICAL CONTEXT:\n  {vocab_block.replace(chr(10), chr(10) + '  ')}"
        planet_briefs.append(brief)

    planets_text = "\n".join(planet_briefs)

    banned_list = ", ".join(BANNED_FOOD_WORDS + BANNED_FABRIC_WORDS)

    prompt = f"""You are writing flavor text for a collectible card game — think Magic: The Gathering "flavor text" at the bottom of a card.

You have {len(pieces_vision)} exoplanet cards. Each one needs ONE line of flavor text.
The text should make someone feel like they're reading a fragment from a surveyor's journal,
a whispered legend, a captain's log, a poet's notebook — varied and alive.

HERE ARE THE PLANETS:
{planets_text}

RULES — follow these absolutely:
1. Each line MUST be under 130 characters
2. Each line MUST use a DIFFERENT voice/perspective — vary between:
   - First person ("I found...", "The scanners showed...")
   - Second person ("You can still see...", "Touch the surface and...")
   - Third person ("The survey team named it...", "No expedition returned...")
   - Fragment/log style ("EXPEDITION LOG — Day 47:", "NOTE: surface temp...")
   - Impersonal/mythic ("They say the rivers run...", "Legend has it...")
   - Question/riddle ("What made the sky turn green?", "Who built these ridges?")
3. Each line MUST reference THIS planet's specific colors/textures — use the GEOLOGICAL CONTEXT provided, NOT raw color names
4. FORBIDDEN WORDS (do NOT use in ANY line): watched, weep, weeping, pool, pooling, cool, cooling, bled, bleed, stain, rain, skin
5. FOOD/FABRIC BAN: do NOT use these words as metaphors: {banned_list}
6. Do NOT start more than 2 lines with the same word
7. NO pottery words: glaze, clay, kiln, firing, thrown, ceramic, pottery
8. NO emojis
9. NO dashes (em dashes, en dashes) in any text — use commas or periods instead
10. When a planet has GEOLOGICAL CONTEXT, use those geological descriptions instead of the raw color/surface names
11. Each distinctive geological term (crystallization, oxidation, compression, etc.) may appear in AT MOST ONE lore line — spread the vocabulary across all planets

Output ONLY a JSON object mapping planet name to lore line:
{{"PlanetName": "lore text", "AnotherPlanet": "lore text"}}"""

    response = client.chat.completions.create(
        model=config.openrouter_caption_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
        temperature=1.0,
    )

    try:
        lore_map = _parse_json_response(response.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError):
        raise RuntimeError(f"Failed to parse lore batch: {response.choices[0].message.content[:300]}")

    # Validate and clean
    result = {}
    for pv in pieces_vision:
        name = pv["planet_name"]
        lore = lore_map.get(name, "").strip().strip('"').strip("'")
        if not lore:
            raise RuntimeError(f"No lore generated for {name}")
        if len(lore) > 130:
            lore = lore[:127] + "..."
        result[name] = lore

    # Check for forbidden word leakage
    all_text = " ".join(result.values()).lower()
    leaked = [w for w in _BANNED_OVERFLOW if w in all_text]
    if leaked:
        if _retry_count >= _MAX_LORE_RETRIES:
            print(f"  WARNING: forbidden words still present after {_MAX_LORE_RETRIES} retries: {leaked} — accepting as-is")
        else:
            print(f"  WARNING: forbidden words in lore: {leaked} — regenerating batch ({_retry_count + 1}/{_MAX_LORE_RETRIES})...")
            return generate_all_lore(pieces_vision, _retry_count=_retry_count + 1)

    # Check word frequency across all lines — flag any word appearing 3+ times
    all_words = " ".join(result.values()).lower().split()
    freq = Counter(all_words)
    # Strip punctuation for counting
    import re
    all_words_clean = re.findall(r"[a-z]+", " ".join(result.values()).lower())
    freq = Counter(all_words_clean)
    overused = {w for w, c in freq.items() if c >= 4 and w not in {"the", "a", "of", "and", "in", "to", "is", "it", "that", "on", "with", "as", "at", "by", "from", "for", "its", "was", "were", "this", "not", "but", "or", "an", "be", "has", "had", "are", "been", "you", "we", "they", "their", "our", "my", "no", "all", "if", "so", "can", "when", "where", "what", "how", "do", "did", "will", "would", "could", "should"}}
    if overused:
        print(f"  NOTE: words used 4+ times (may be fine): {overused}")

    return result


def generate_worldbuilding(
    hypotheses, surface_qualities, primary_colors, secondary_colors,
    form_attributes, mood, technique, clay_type, firing_state,
    color_appearance, planet_name, lore_line=None, _retry_count=0,
) -> dict:
    """
    Call AI to generate 4 worldbuilding fields from ceramic vision data.
    formation_history is passed in (from batch lore generation) rather than generated here.

    Returns dict with keys:
      surface_geology, orbital_data, formation_history, inhabitants, generated_caption
    """
    client, config = _get_client()

    hypotheses_list = hypotheses if isinstance(hypotheses, list) else (
        json.loads(hypotheses) if hypotheses else []
    )
    hypotheses_text = "; ".join(h[:200] for h in hypotheses_list[:4]) if hypotheses_list else "unknown"

    # Build vocabulary block from actual detected colors/surfaces
    colors_parsed = primary_colors if isinstance(primary_colors, list) else (
        json.loads(primary_colors) if primary_colors else []
    )
    surfaces_parsed = surface_qualities if isinstance(surface_qualities, list) else (
        json.loads(surface_qualities) if surface_qualities else []
    )
    vocab_block = build_vocabulary_block(colors_parsed, surfaces_parsed, mood)
    banned_list = ", ".join(BANNED_FOOD_WORDS + BANNED_FABRIC_WORDS)

    vocab_section = ""
    if vocab_block:
        vocab_section = f"""
GEOLOGICAL VOCABULARY — use these descriptions for the colors/surfaces above:
{vocab_block}

IMPORTANT: When describing the planet's colors or surfaces, use the GEOLOGICAL VOCABULARY descriptions above.
For example, if "denim" is detected, write "cobalt-iron oxidation" NOT "denim atmosphere".
If "chocolate" is detected, write "dense organic matter compressed with iron oxides" NOT "chocolate stone".
"""

    prompt = f"""You are a planetary survey AI writing an exploration dossier for exoplanet {planet_name}.

The planet's surface was imaged by a deep-space probe. Here is the analysis:

COLORS: {_fmt_list(primary_colors)}
SURFACE TEXTURES: {_fmt_list(surface_qualities)}
FORM/TOPOGRAPHY: {_fmt_list(form_attributes)}
MOOD: {_clean(mood) if mood else 'unknown'}
SURFACE DESCRIPTION: {_clean(color_appearance) if color_appearance else 'unknown'}
SURVEYOR HYPOTHESES: {hypotheses_text}
{vocab_section}
The lore line for this planet has already been written:
"{lore_line or '(none)'}"

Generate a planetary exploration dossier. Output ONLY valid JSON with these 4 fields:

{{
  "surface_geology": "2-3 sentences describing the planet's surface geology. Reference the ACTUAL colors, textures, and landforms from the analysis. Sound like a geologist's field report.",
  "orbital_data": "Atmospheric composition and conditions. Include Atmosphere, Breathability (SURVIVABLE/TOXIC/LETHAL), Suit requirements, Temperature, and Scent. Format each on its own line with colon separator.",
  "inhabitants": "Life report with sections: WHAT IT FEELS LIKE TO BE THERE, INTELLIGENT LIFE, ANIMAL LIFE, PLANT LIFE. Base everything on the actual surface analysis — colors, textures, mood. Be creative but grounded.",
  "generated_caption": "Instagram caption under 280 characters. Mention the planet name and a striking visual detail. End with a question to drive engagement."
}}

STRICT RULES:
- Use the ACTUAL colors and textures from the analysis — do NOT invent colors or materials not mentioned above
- When the GEOLOGICAL VOCABULARY section is present, use those geological descriptions INSTEAD of raw color/surface names
- FOOD/FABRIC BAN: do NOT use these words as metaphors or descriptors: {banned_list}
- NO pottery words: glaze, clay, kiln, firing, thrown, ceramic, pottery, wheel, glazes
- NO dashes (em dashes, en dashes) — use commas or periods instead
- generated_caption MUST be under 280 characters
- Output ONLY the JSON object, no markdown fences, no explanation"""

    response = client.chat.completions.create(
        model=config.openrouter_caption_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=800,
        temperature=0.8,
    )

    wb = _parse_json_response(response.choices[0].message.content.strip())

    required = ["surface_geology", "orbital_data", "inhabitants", "generated_caption"]
    missing = [k for k in required if k not in wb or not wb[k]]
    if missing:
        raise RuntimeError(f"AI missing fields for {planet_name}: {missing}")

    if len(wb["generated_caption"]) > 280:
        wb["generated_caption"] = wb["generated_caption"][:277] + "..."

    # Set the lore line
    wb["formation_history"] = lore_line or ""

    # Check for pottery term leakage
    forbidden = ["glaze", "clay", "kiln", "firing", "thrown", "ceramic", "pottery"]
    all_text = " ".join(wb.values()).lower()
    leaked = [w for w in forbidden if w in all_text]
    if leaked and _retry_count < _MAX_WB_RETRIES:
        print(f"  WARNING {planet_name}: pottery terms leaked: {leaked} — regenerating ({_retry_count + 1}/{_MAX_WB_RETRIES})...")
        return generate_worldbuilding(
            hypotheses, surface_qualities, primary_colors, secondary_colors,
            form_attributes, mood, technique, clay_type, firing_state,
            color_appearance, planet_name, lore_line=lore_line, _retry_count=_retry_count + 1,
        )
    elif leaked:
        print(f"  WARNING {planet_name}: pottery terms still present after {_MAX_WB_RETRIES} retries: {leaked} — accepting as-is")

    # Check for food/fabric word leakage
    food_fabric_leaked = check_banned_words(all_text)
    if food_fabric_leaked and _retry_count < _MAX_WB_RETRIES:
        print(f"  WARNING {planet_name}: food/fabric words leaked: {food_fabric_leaked} — regenerating ({_retry_count + 1}/{_MAX_WB_RETRIES})...")
        return generate_worldbuilding(
            hypotheses, surface_qualities, primary_colors, secondary_colors,
            form_attributes, mood, technique, clay_type, firing_state,
            color_appearance, planet_name, lore_line=lore_line, _retry_count=_retry_count + 1,
        )
    elif food_fabric_leaked:
        print(f"  WARNING {planet_name}: food/fabric words still present after {_MAX_WB_RETRIES} retries: {food_fabric_leaked} — accepting as-is")

    return wb
