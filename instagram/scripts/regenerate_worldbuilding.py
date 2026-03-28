#!/usr/bin/env python3
"""
Regenerate worldbuilding for all series pieces.
Phase 1: Generate all lore lines in one AI call (ensures diversity)
Phase 2: Generate remaining fields per-piece with lore as context
POSTs results back to API.
"""
import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"
API_BASE = "http://localhost:8766"

# Ensure project root is on sys.path
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from lib.worldbuilding_generator import generate_all_lore, generate_worldbuilding


def safe_json_parse(raw):
    if not raw:
        return []
    try:
        result = json.loads(raw)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def gather_vision_data(conn, piece):
    """Union-merge all vision results for a photo."""
    base_name = Path(piece["photo"]).stem

    all_vr = conn.execute("""
        SELECT vr.mood, vr.primary_colors, vr.color_appearance,
               vr.surface_qualities, vr.form_attributes, vr.technique,
               vr.clay_type, vr.glaze_type, vr.hypotheses
        FROM vision_results vr
        JOIN photos p ON vr.photo_id = p.id
        WHERE p.filename LIKE ?
    """, (f"%{base_name}%",)).fetchall()

    if not all_vr:
        return None

    merged = {}
    ARRAY_FIELDS = ['primary_colors', 'surface_qualities', 'form_attributes', 'hypotheses']
    TEXT_FIELDS = ['color_appearance']
    SCALAR_FIELDS = ['mood', 'technique', 'clay_type', 'glaze_type']

    for key in ARRAY_FIELDS:
        union = []
        seen = set()
        for row in all_vr:
            for item in safe_json_parse(row[key]):
                if item not in seen:
                    seen.add(item)
                    union.append(item)
        merged[key] = json.dumps(union) if union else None

    for key in TEXT_FIELDS:
        longest = None
        for row in all_vr:
            val = row[key]
            if val and (longest is None or len(val) > len(longest)):
                longest = val
        merged[key] = longest

    for key in SCALAR_FIELDS:
        val = None
        for row in all_vr:
            if row[key]:
                val = row[key]
                break
        merged[key] = val

    return merged


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    pieces = conn.execute("""
        SELECT sp.id, sp.photo, sp.planet_name, sp.series_id, sp.order_index
        FROM series_pieces sp
        ORDER BY sp.order_index
    """).fetchall()

    print(f"Found {len(pieces)} series pieces.\n")

    # --- Gather all vision data ---
    vision_map = {}  # planet_name -> merged vision dict
    for piece in pieces:
        vr = gather_vision_data(conn, piece)
        if not vr:
            print(f"SKIP {piece['planet_name']} ({piece['photo']}): no vision data")
            continue
        vision_map[piece["planet_name"]] = {
            "piece": piece,
            "vr": vr,
        }

    valid_planets = list(vision_map.keys())
    if not valid_planets:
        print("No pieces with vision data. Exiting.")
        conn.close()
        return

    # --- PHASE 1: Generate all lore lines in one batch ---
    print("Phase 1: Generating all lore lines in one batch...")
    lore_briefs = []
    for name, data in vision_map.items():
        vr = data["vr"]
        hypotheses = safe_json_parse(vr.get("hypotheses") or "[]")
        lore_briefs.append({
            "planet_name": name,
            "colors": _fmt(safe_json_parse(vr.get("primary_colors") or "[]")),
            "textures": _fmt(safe_json_parse(vr.get("surface_qualities") or "[]")),
            "mood": _clean(vr.get("mood")),
            "form": _fmt(safe_json_parse(vr.get("form_attributes") or "[]")),
            "description": vr.get("color_appearance"),
            "hypotheses": "; ".join(h[:120] for h in hypotheses[:3]) if hypotheses else None,
        })

    try:
        lore_map = generate_all_lore(lore_briefs)
    except RuntimeError as e:
        print(f"FATAL: Lore generation failed: {e}")
        conn.close()
        return

    print(f"\nLore lines ({len(lore_map)}):")
    for name, lore in lore_map.items():
        print(f"  {name}: {lore} ({len(lore)} chars)")
    print()

    # --- PHASE 2: Generate remaining fields per piece ---
    print("Phase 2: Generating worldbuilding fields per piece...\n")

    import urllib.request

    for name, data in vision_map.items():
        piece = data["piece"]
        vr = data["vr"]
        lore = lore_map.get(name)

        if not lore:
            print(f"SKIP {name}: no lore generated")
            continue

        try:
            wb = generate_worldbuilding(
                hypotheses=vr.get("hypotheses"),
                surface_qualities=vr.get("surface_qualities"),
                primary_colors=vr.get("primary_colors"),
                secondary_colors=[],
                form_attributes=vr.get("form_attributes"),
                mood=vr.get("mood"),
                technique=vr.get("technique"),
                clay_type=vr.get("clay_type"),
                firing_state=None,
                color_appearance=vr.get("color_appearance"),
                planet_name=name,
                lore_line=lore,
            )
        except RuntimeError as e:
            print(f"ERROR {name}: {e}")
            continue

        # POST to API
        payload = json.dumps({
            "series_id": piece["series_id"],
            "photo": piece["photo"],
            "planet_name": name,
            "orbital_data": wb["orbital_data"],
            "surface_geology": wb["surface_geology"],
            "formation_history": wb["formation_history"],
            "inhabitants": wb["inhabitants"],
            "generated_caption": wb["generated_caption"],
        }).encode()

        req = urllib.request.Request(
            f"{API_BASE}/api/series-piece",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            resp = urllib.request.urlopen(req)
        except Exception as e:
            print(f"ERROR {name}: API call failed: {e}")
            continue

        # Quality check
        orbital = wb.get("orbital_data", "")
        breathability = "unknown"
        for line in orbital.split("\n"):
            if line.startswith("Breathability:"):
                breathability = line.split(":", 1)[1].strip()
                break

        print(f"OK {name} ({piece['photo']})")
        print(f"   Breathability: {breathability}")
        print(f"   Lore ({len(lore)} chars): {lore}")
        print(f"   Caption: {wb['generated_caption'][:80]}...")
        print()

    conn.close()
    print("Done.")


def _fmt(items):
    """Quick format list for lore briefs."""
    if not items:
        return "unknown"
    return ", ".join(str(i) for i in items[:6])


def _clean(text):
    """Replace underscores."""
    if not text:
        return "unknown"
    replacements = {
        "slate_blue": "slate blue", "chun_blue": "deep blue", "seafoam": "seafoam green",
        "oxblood": "oxblood red", "earth_tones": "earth tones", "ice_blue": "ice blue",
        "dark_blue": "dark blue",
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text.replace("_", " ")


if __name__ == "__main__":
    main()
