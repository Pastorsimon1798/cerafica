#!/usr/bin/env python3
"""
Generate planetary-themed captions for the Glaze Exploration Series.

Reads worldbuilding data from series_pieces table and vision data from vision_results,
then generates captions that weave together:
- Planet name from worldbuilding
- Surface qualities from vision analysis
- Geological story from worldbuilding
- Inhabitant lore from worldbuilding

Updates series_pieces.generated_caption with the result.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

# Load .env file for API keys
_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    for line in _env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from caption_generator import get_ai_config

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"


PLANETARY_CAPTION_PROMPT = """You are writing Instagram captions for handcrafted ceramics in a planetary exploration theme.

PLANET DATA:
- Planet Name: {planet_name}
- Atmosphere: {orbital_data}
- Surface Geology: {surface_geology}
- Formation History: {formation_history}
- Inhabitants/Lore: {inhabitants}

VISUAL DESCRIPTION (what the surface actually looks like):
- Surface Appearance: {surface_appearance}
- Surface Textures: {surface_qualities}
- Chemistry Notes: {chemistry_notes}
- Visual Analysis: {hypotheses}

IMPORTANT: Use geological and chemical terminology (oxides, silicates, iron, copper, carbon deposits, crystallization, mineral stratification). NEVER use casual color names like "denim", "chocolate", "oatmeal", or fabric/food references.

{creative_direction}
Write ONE caption (under 280 characters) that:
1. Names the planet (use the actual name: {planet_name})
2. Describes terrain using the chemistry identified in the visual analysis above
3. Hints at the inhabitant lore mysteriously
4. Ends with an engaging question
5. NO emojis (user adds those later)

CHEMISTRY GUIDANCE:
- Use the Chemistry Notes and Visual Analysis fields above as your PRIMARY source
- These contain the actual oxide compounds and chemical processes identified in the piece
- If Chemistry Notes mention specific compounds (e.g., "copper oxide", "iron oxide"), use those exact terms
- If no chemistry data is provided, fall back to visible color inference:
  - Blue/green → copper compounds
  - Rust/brown → iron oxidation
  - Black/charcoal → carbon deposits
  - Purple/plum → manganese compounds

TEXTURE → GEOLOGY MAPPING:
- crawling → tectonic movement patterns
- variegation → mineral stratification
- luster → metallic crystallization
- speckled → meteoritic inclusions
- rivulets → lava flow channels
- crackle → thermal shock fractures
- gloss → rapid cooling (glassy)
- satin → slow erosion smoothing

CRITICAL RULES:
- Describe what you SEE, not what glaze it might be
- NEVER mention glaze names
- Prefer chemistry from the analysis over generic color→compound mapping
- Science must match the visible reality

Output ONLY the caption text, nothing else."""


def get_planet_data(db_path: Path) -> list[dict]:
    """Get worldbuilding data for all photos in series 1."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, photo, planet_name, orbital_data, surface_geology,
               formation_history, inhabitants, generated_caption
        FROM series_pieces
        WHERE series_id = 1
        ORDER BY order_index
    """)

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_vision_data(db_path: Path, photo_filename: str) -> dict:
    """Get vision analysis data for a photo (latest result)."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Get photo ID
    cursor.execute("SELECT id FROM photos WHERE filename = ?", (photo_filename,))
    photo_row = cursor.fetchone()
    if not photo_row:
        conn.close()
        return {}

    photo_id = photo_row["id"]

    # Get vision result (prefer Kimi/Gemini over OpenRouter - better surface detection)
    cursor.execute("""
        SELECT model, glaze_type, primary_colors, secondary_colors,
               surface_qualities, form_attributes, color_appearance, hypotheses,
               piece_type, mood, technique, firing_state, clay_type
        FROM vision_results
        WHERE photo_id = ?
        ORDER BY CASE WHEN model LIKE 'Kimi%' THEN 0 WHEN model LIKE 'Gemini%' THEN 1 ELSE 2 END,
                 (color_appearance IS NOT NULL) DESC,
                 created_at DESC
        LIMIT 1
    """, (photo_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return {}

    return {
        "model": row["model"],
        "glaze_type": row["glaze_type"],
        "primary_colors": json.loads(row["primary_colors"]) if row["primary_colors"] else [],
        "secondary_colors": json.loads(row["secondary_colors"]) if row["secondary_colors"] else [],
        "surface_qualities": json.loads(row["surface_qualities"]) if row["surface_qualities"] else [],
        "form_attributes": json.loads(row["form_attributes"]) if row["form_attributes"] else [],
        "color_appearance": row["color_appearance"] or "",
        "hypotheses": json.loads(row["hypotheses"]) if row["hypotheses"] else [],
        "piece_type": row["piece_type"],
        "mood": row["mood"],
        "technique": row["technique"],
        "firing_state": row["firing_state"],
        "clay_type": row["clay_type"],
    }


def generate_caption_openrouter(planet_data: dict, vision_data: dict, creative_direction: str = "") -> str:
    """Generate planetary caption using OpenRouter API."""
    from openai import OpenAI

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    config = get_ai_config()

    prompt = PLANETARY_CAPTION_PROMPT.format(
        planet_name=planet_data["planet_name"] or "Unknown",
        orbital_data=planet_data["orbital_data"] or "Unknown",
        surface_geology=planet_data["surface_geology"] or "Unknown",
        formation_history=planet_data["formation_history"] or "Unknown",
        inhabitants=planet_data["inhabitants"] or "Unknown",
        surface_appearance=vision_data.get("color_appearance", "Not available"),
        surface_qualities=", ".join(vision_data.get("surface_qualities", [])),
        chemistry_notes=vision_data.get("color_appearance", "Not available"),
        hypotheses=", ".join(vision_data.get("hypotheses", [])) if isinstance(vision_data.get("hypotheses"), list) else str(vision_data.get("hypotheses", "")),
        creative_direction=creative_direction,
    )

    client = OpenAI(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    response = client.chat.completions.create(
        model=config.openrouter_caption_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=300
    )

    return response.choices[0].message.content.strip()


def update_caption(db_path: Path, piece_id: int, caption: str):
    """Update the generated_caption field for a series piece."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE series_pieces
        SET generated_caption = ?
        WHERE id = ?
    """, (caption, piece_id))

    conn.commit()
    conn.close()


def main():
    """Generate and update planetary captions for all photos in series 1."""
    print("=" * 60)
    print("Planetary Caption Generator")
    print("=" * 60)

    # Get all planet data
    planets = get_planet_data(DB_PATH)
    print(f"\nFound {len(planets)} photos in Glaze Exploration Series")

    # Target all photos in the series
    print(f"Targeting all {len(planets)} photos in series\n")

    for planet in planets:
        print(f"\n--- {planet['photo']} ---")
        print(f"Planet: {planet['planet_name']}")
        print(f"Current caption: {(planet['generated_caption'] or 'None')[:80]}...")

        # Get vision data
        vision = get_vision_data(DB_PATH, planet["photo"])
        if not vision:
            print(f"  WARNING: No vision data found, skipping")
            continue

        print(f"Colors: {vision.get('primary_colors')}")
        print(f"Surface: {vision.get('surface_qualities')}")

        # Generate new caption
        print("Generating caption...")
        try:
            caption = generate_caption_openrouter(planet, vision)
            print(f"New caption: {caption}")

            # Update database
            update_caption(DB_PATH, planet["id"], caption)
            print("  Updated database")

        except Exception as e:
            print(f"  ERROR: {e}")
            continue

    print("\n" + "=" * 60)
    print("Done! Verify captions at http://100.97.231.117:8766/")
    print("=" * 60)


if __name__ == "__main__":
    main()
