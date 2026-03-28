#!/usr/bin/env python3
"""
One-off script to populate feedback.db for ceruleix-2 and run the full
vision → worldbuilding pipeline so frame_video.py can use the data.

Steps:
  1. Init DB with proper schema (from feedback/server.py)
  2. Run migration for extra vision_results columns
  3. Insert photo record for ceruleix-2.jpg
  4. Run vision analysis via analyze_photo()
  5. Store vision results
  6. Insert series entry
  7. Generate worldbuilding (lore + dossier) via AI
  8. Store worldbuilding in series_pieces
"""

import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "instagram" / "scripts" / "lib"))

from caption_generator import (
    analyze_photo,
    get_ai_config,
    set_ai_config,
    AIConfig,
    PhotoAnalysis,
)
from worldbuilding_generator import generate_all_lore, generate_worldbuilding

DB_PATH = Path(__file__).parent / "feedback.db"
PHOTO_PATH = Path(__file__).parent.parent / "inventory" / "available" / "ceruleix-2.jpg"
PLANET_NAME = "ceruleix-2"
SERIES_NAME = "Ceruleix Collection"
SERIES_ID = 1


def init_db():
    """Create tables matching feedback/server.py schema (the real one frame_video.py expects)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            worldbuilding_prompt TEXT,
            frame_style TEXT DEFAULT 'planetary',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS series_pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER NOT NULL,
            photo TEXT NOT NULL,
            planet_name TEXT,
            orbital_data TEXT,
            surface_geology TEXT,
            formation_history TEXT,
            inhabitants TEXT,
            generated_caption TEXT,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (series_id) REFERENCES series(id),
            UNIQUE(series_id, photo)
        )
    ''')

    # Photos table (from server.py — simpler than auto_vision.py's)
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            post_format TEXT DEFAULT 'photo',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Vision results table (from auto_vision.py)
    c.execute('''
        CREATE TABLE IF NOT EXISTS vision_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            piece_type TEXT,
            glaze_type TEXT,
            primary_colors TEXT,
            secondary_colors TEXT,
            surface_qualities TEXT,
            mood TEXT,
            form_attributes TEXT,
            firing_state TEXT,
            technique TEXT,
            content_type TEXT,
            piece_count INTEGER DEFAULT 1,
            hypotheses TEXT,
            vision_reasoning TEXT,
            raw_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (photo_id) REFERENCES photos(id),
            UNIQUE(photo_id, model)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"[OK] Database initialized: {DB_PATH}")


def migrate_db():
    """Add extra columns to vision_results (from auto_vision.py migrate_db)."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for col in ['color_appearance', 'brief_description', 'clay_type', 'purpose',
                 'product_family', 'dimensions_visible', 'lighting', 'photo_quality',
                 'uncertainties', 'color_distribution']:
        try:
            c.execute(f'ALTER TABLE vision_results ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()
    print("[OK] Migrations applied")


def get_photo_id(filename: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM photos WHERE filename = ?', (filename,))
    row = c.fetchone()
    if row:
        photo_id = row[0]
    else:
        c.execute('INSERT INTO photos (filename) VALUES (?)', (filename,))
        conn.commit()
        photo_id = c.lastrowid
    conn.close()
    return photo_id


def save_vision_result(photo_id: int, model: str, analysis: PhotoAnalysis):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT OR REPLACE INTO vision_results
        (photo_id, model, piece_type, glaze_type, primary_colors, secondary_colors,
         surface_qualities, mood, form_attributes, firing_state, technique,
         content_type, piece_count, hypotheses,
         color_appearance, brief_description, clay_type, purpose,
         product_family, dimensions_visible, lighting, photo_quality,
         uncertainties, color_distribution)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        photo_id, model,
        analysis.piece_type,
        analysis.glaze_type,
        json.dumps(analysis.primary_colors) if analysis.primary_colors else None,
        json.dumps(analysis.secondary_colors) if analysis.secondary_colors else None,
        json.dumps(analysis.surface_qualities) if analysis.surface_qualities else None,
        analysis.mood,
        json.dumps(analysis.form_attributes) if analysis.form_attributes else None,
        analysis.firing_state,
        analysis.technique,
        analysis.content_type.value if analysis.content_type else None,
        analysis.piece_count,
        json.dumps(analysis.hypotheses) if hasattr(analysis, 'hypotheses') and analysis.hypotheses else None,
        getattr(analysis, 'color_appearance', None),
        getattr(analysis, 'brief_description', None),
        getattr(analysis, 'clay_type', None),
        getattr(analysis, 'purpose', None),
        getattr(analysis, 'product_family', None),
        getattr(analysis, 'dimensions_visible', None),
        json.dumps(analysis.lighting) if hasattr(analysis, 'lighting') and analysis.lighting else None,
        json.dumps(analysis.photo_quality) if hasattr(analysis, 'photo_quality') and analysis.photo_quality else None,
        json.dumps(analysis.uncertainties) if hasattr(analysis, 'uncertainties') and analysis.uncertainties else None,
        getattr(analysis, 'color_distribution', None),
    ))
    conn.commit()
    conn.close()


def main():
    print("=" * 60)
    print("SETUP: ceruleix-2 for video framing pipeline")
    print("=" * 60)

    # --- Step 1: Init DB ---
    print("\n[1/6] Initializing database...")
    init_db()
    migrate_db()

    # --- Step 2: Insert photo ---
    print(f"\n[2/6] Registering photo: {PHOTO_PATH.name}")
    assert PHOTO_PATH.exists(), f"Photo not found: {PHOTO_PATH}"
    photo_id = get_photo_id(PHOTO_PATH.name)
    print(f"       photo_id = {photo_id}")

    # --- Step 3: Check if vision already exists ---
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM vision_results WHERE photo_id = ?', (photo_id,))
    existing = c.fetchone()
    conn.close()

    if existing:
        print("\n[3/6] Vision analysis already exists, skipping...")
        # Load existing vision data
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM vision_results WHERE photo_id = ? LIMIT 1', (photo_id,))
        row = c.fetchone()
        conn.close()
        primary_colors = json.loads(row["primary_colors"]) if row["primary_colors"] else []
        secondary_colors = json.loads(row["secondary_colors"]) if row["secondary_colors"] else []
        surface_qualities = json.loads(row["surface_qualities"]) if row["surface_qualities"] else []
        form_attributes = json.loads(row["form_attributes"]) if row["form_attributes"] else []
        hypotheses = json.loads(row["hypotheses"]) if row["hypotheses"] else []
        mood = row["mood"]
        technique = row["technique"]
        clay_type = row["clay_type"]
        firing_state = row["firing_state"]
        color_appearance = row["color_appearance"]
    else:
        # --- Step 3: Run vision analysis ---
        print("\n[3/6] Running vision analysis (Ollama kimi-k2.5)...")
        # Use default AI config (Ollama)
        config = get_ai_config()
        print(f"       backend={config.backend}, vision_model={config.ollama_vision_model}")

        analysis = analyze_photo(str(PHOTO_PATH))
        print(f"       piece_type: {analysis.piece_type}")
        print(f"       mood: {analysis.mood}")
        print(f"       colors: {analysis.primary_colors[:5]}")
        print(f"       surfaces: {analysis.surface_qualities[:5]}")
        print(f"       hypotheses: {analysis.hypotheses[:3]}")

        # Save to DB
        save_vision_result(photo_id, "Kimi K2.5", analysis)
        print("       [OK] Vision results saved")

        primary_colors = analysis.primary_colors
        secondary_colors = analysis.secondary_colors
        surface_qualities = analysis.surface_qualities
        form_attributes = analysis.form_attributes
        hypotheses = analysis.hypotheses
        mood = analysis.mood
        technique = analysis.technique
        clay_type = getattr(analysis, 'clay_type', None)
        firing_state = analysis.firing_state
        color_appearance = getattr(analysis, 'color_appearance', None)

    # --- Step 4: Insert series ---
    print(f"\n[4/6] Ensuring series exists: {SERIES_NAME}")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO series (id, name, description) VALUES (?, ?, ?)',
              (SERIES_ID, SERIES_NAME, "Ceruleix glaze exploration pieces"))
    conn.commit()
    conn.close()

    # --- Step 5: Check if worldbuilding already exists ---
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id FROM series_pieces WHERE planet_name = ?', (PLANET_NAME,))
    existing_wb = c.fetchone()
    conn.close()

    if existing_wb:
        print(f"\n[5/6] Worldbuilding for {PLANET_NAME} already exists, skipping...")
        # Load and display
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute('SELECT * FROM series_pieces WHERE planet_name = ?', (PLANET_NAME,))
        row = c.fetchone()
        conn.close()
        print(f"       lore: {row['formation_history'][:80]}...")
        print(f"       caption: {row['generated_caption'][:80]}...")
    else:
        # --- Step 5: Generate worldbuilding ---
        print(f"\n[5/6] Generating worldbuilding for {PLANET_NAME}...")

        # Phase 1: Lore generation
        piece_vision = {
            "planet_name": PLANET_NAME,
            "colors": ", ".join(primary_colors) if primary_colors else "unknown",
            "textures": ", ".join(surface_qualities) if surface_qualities else "unknown",
            "mood": mood or "unknown",
            "form": form_attributes[0] if form_attributes else "vessel",
            "description": color_appearance or "",
            "hypotheses": "; ".join(hypotheses[:3]) if hypotheses else "",
        }
        print("       Phase 1: Generating lore line...")
        lore_map = generate_all_lore([piece_vision])
        lore_line = lore_map.get(PLANET_NAME, "")
        print(f"       lore: {lore_line}")

        # Phase 2: Full worldbuilding dossier
        print("       Phase 2: Generating worldbuilding dossier...")
        wb_dict = generate_worldbuilding(
            hypotheses=hypotheses,
            surface_qualities=surface_qualities,
            primary_colors=primary_colors,
            secondary_colors=secondary_colors,
            form_attributes=form_attributes,
            mood=mood,
            technique=technique,
            clay_type=clay_type,
            firing_state=firing_state,
            color_appearance=color_appearance,
            planet_name=PLANET_NAME,
            lore_line=lore_line,
        )
        print(f"       geology: {wb_dict['surface_geology'][:60]}...")
        print(f"       caption: {wb_dict['generated_caption'][:60]}...")

        # Store in series_pieces
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO series_pieces
                (series_id, photo, planet_name, surface_geology, orbital_data,
                 formation_history, inhabitants, generated_caption, order_index)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            SERIES_ID,
            PHOTO_PATH.name,
            PLANET_NAME,
            wb_dict["surface_geology"],
            wb_dict["orbital_data"],
            wb_dict["formation_history"],
            wb_dict.get("inhabitants", ""),
            wb_dict["generated_caption"],
            2,  # order_index
        ))
        conn.commit()
        conn.close()
        print("       [OK] Worldbuilding stored in DB")

    # --- Step 6: Verify ---
    print("\n[6/6] Verifying DB state...")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Check photo
    c.execute('SELECT id, filename FROM photos WHERE filename = ?', (PHOTO_PATH.name,))
    photo_row = c.fetchone()
    print(f"       photo: id={photo_row['id']}, filename={photo_row['filename']}")

    # Check vision
    c.execute('SELECT COUNT(*) as cnt FROM vision_results WHERE photo_id = ?', (photo_id,))
    vision_count = c.fetchone()['cnt']
    print(f"       vision_results: {vision_count} row(s)")

    # Check series_pieces
    c.execute('SELECT planet_name, orbital_data, surface_geology, formation_history, generated_caption FROM series_pieces WHERE planet_name = ?', (PLANET_NAME,))
    sp_row = c.fetchone()
    if sp_row:
        print(f"       series_pieces: planet={sp_row['planet_name']}")
        print(f"         orbital_data: {'YES' if sp_row['orbital_data'] else 'MISSING'}")
        print(f"         surface_geology: {'YES' if sp_row['surface_geology'] else 'MISSING'}")
        print(f"         formation_history: {'YES' if sp_row['formation_history'] else 'MISSING'}")
        print(f"         generated_caption: {'YES' if sp_row['generated_caption'] else 'MISSING'}")
    else:
        print("       series_pieces: MISSING!")

    conn.close()
    print("\n" + "=" * 60)
    print("SETUP COMPLETE — ready to run frame_video.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
