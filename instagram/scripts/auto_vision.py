#!/usr/bin/env python3
"""
Auto Vision Runner - Stage 1 of the pipeline.

Watches "To Post" album and runs vision analysis on new photos.
Stores results to database for later caption generation.

Usage:
    python auto_vision.py              # Run once, process all new photos
    python auto_vision.py --watch      # Continuous watch mode
    python auto_vision.py --force      # Re-analyze all photos
"""

import sys
import json
import sqlite3
import argparse
import time
import shutil
import concurrent.futures
import threading
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from photo_export import get_media_from_album, export_media_by_id, MediaType
from caption_generator import (
    analyze_photo,  # Dispatcher that routes based on config
    set_ai_config,
    AIConfig,
    PhotoAnalysis,
)

# =============================================================================
# CONFIGURATION
# =============================================================================

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"
EXPORT_DIR = Path(__file__).parent.parent.parent / "output" / "vision_exports"
PHOTOS_DIR = Path(__file__).parent.parent.parent / "output" / "ab_test_photos"

# Thread lock for serialized DB access from concurrent workers
_db_lock = threading.Lock()

# Vision model configuration - distributed round-robin across providers
MODELS = [
    {"name": "Kimi K2.5 (Ollama)", "backend": "ollama", "vision_model": "kimi-k2.5:cloud"},
    {"name": "Kimi K2.5 (OpenRouter)", "backend": "openrouter", "vision_model": "moonshotai/kimi-k2.5"},
    {"name": "Gemini 3 Flash", "backend": "openrouter", "vision_model": "google/gemini-3-flash-preview"},
]


# =============================================================================
# DATABASE
# =============================================================================

def init_db():
    """Initialize the pipeline database."""
    conn = sqlite3.connect(DB_PATH, timeout=30)
    c = conn.cursor()

    # Use WAL mode for better concurrent read/write access
    c.execute('PRAGMA journal_mode=WAL')

    # Photos table - tracks what's been analyzed
    c.execute('''
        CREATE TABLE IF NOT EXISTS photos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            status TEXT DEFAULT 'new',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            analyzed_at TIMESTAMP
        )
    ''')

    # Vision results - one row per photo per model
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

    # Idea seeds - user creative associations
    c.execute('''
        CREATE TABLE IF NOT EXISTS idea_seeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            seed_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (photo_id) REFERENCES photos(id)
        )
    ''')

    # Creative direction - per-photo guidance
    c.execute('''
        CREATE TABLE IF NOT EXISTS creative_direction (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL UNIQUE,
            direction_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (photo_id) REFERENCES photos(id)
        )
    ''')

    # Series
    c.execute('''
        CREATE TABLE IF NOT EXISTS series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            worldbuilding_prompt TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Series pieces - links photos to series
    c.execute('''
        CREATE TABLE IF NOT EXISTS series_pieces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id INTEGER NOT NULL,
            photo_id INTEGER NOT NULL,
            planet_name TEXT,
            generated_worldbuilding TEXT,
            order_index INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (series_id) REFERENCES series(id),
            FOREIGN KEY (photo_id) REFERENCES photos(id),
            UNIQUE(series_id, photo_id)
        )
    ''')

    # Caption results - one row per photo per model
    c.execute('''
        CREATE TABLE IF NOT EXISTS caption_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            photo_id INTEGER NOT NULL,
            model TEXT NOT NULL,
            hook TEXT,
            body TEXT,
            cta TEXT,
            full_caption TEXT,
            caption_reasoning TEXT,
            raw_response TEXT,
            is_winner INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (photo_id) REFERENCES photos(id),
            UNIQUE(photo_id, model)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"✓ Database initialized: {DB_PATH}")


def migrate_db():
    """Add missing columns to existing tables."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for col in ['color_appearance', 'brief_description', 'clay_type', 'purpose',
                 'product_family', 'dimensions_visible', 'lighting', 'photo_quality',
                 'uncertainties', 'color_distribution']:
        try:
            c.execute(f'ALTER TABLE vision_results ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass  # Column already exists

    conn.commit()
    conn.close()


def get_photo_id(filename: str) -> int:
    """Get or create photo ID for a filename."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()

        # INSERT OR IGNORE is atomic - avoids race between SELECT and INSERT
        c.execute('INSERT OR IGNORE INTO photos (filename, status) VALUES (?, ?)',
                  (filename, 'new'))
        conn.commit()

        c.execute('SELECT id FROM photos WHERE filename = ?', (filename,))
        photo_id = c.fetchone()[0]

        conn.close()
        return photo_id


def has_vision_result(photo_id: int, model: str) -> bool:
    """Check if vision result already exists for this photo/model."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()
        c.execute('SELECT id FROM vision_results WHERE photo_id = ? AND model = ?',
                  (photo_id, model))
        exists = c.fetchone() is not None
        conn.close()
        return exists


def save_vision_result(photo_id: int, model: str, analysis: PhotoAnalysis,
                       reasoning: str, raw_response: str):
    """Save vision analysis result to database."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        c = conn.cursor()

        c.execute('''
            INSERT OR REPLACE INTO vision_results
            (photo_id, model, piece_type, glaze_type, primary_colors, secondary_colors,
             surface_qualities, mood, form_attributes, firing_state, technique,
             content_type, piece_count, hypotheses, vision_reasoning, raw_response,
             color_appearance, brief_description, clay_type, purpose,
             product_family, dimensions_visible, lighting, photo_quality,
             uncertainties, color_distribution)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            photo_id,
            model,
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
            reasoning,
            raw_response,
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

        # Update photo status
        c.execute('UPDATE photos SET status = ?, analyzed_at = ? WHERE id = ?',
                  ('analyzed', datetime.now().isoformat(), photo_id))

        conn.commit()
        conn.close()


# =============================================================================
# VISION ANALYSIS
# =============================================================================

def analyze_with_model(photo_path: Path, config: dict) -> tuple[PhotoAnalysis, str, str]:
    """
    Run vision analysis with the configured model.

    Routes to appropriate backend based on config.

    Returns:
        (PhotoAnalysis, reasoning_text, raw_response)
    """
    if config["backend"] == "ollama":
        set_ai_config(AIConfig(
            backend="ollama",
            ollama_vision_model=config["vision_model"],
        ))
    else:
        set_ai_config(AIConfig(
            backend="openrouter",
            openrouter_vision_model=config["vision_model"],
        ))

    result = analyze_photo(str(photo_path))
    return result, "", ""


def process_photo(photo_path: Path, model: dict, force: bool = False) -> dict:
    """
    Run vision analysis on a single photo with a specific model.

    Returns:
        Dict with result from the assigned model
    """
    filename = photo_path.name
    photo_id = get_photo_id(filename)
    model_name = model["name"]

    result = {
        "photo": filename,
        "photo_id": photo_id,
        "model": model_name,
    }

    if not force and has_vision_result(photo_id, model_name):
        result["status"] = "skipped"
        print(f"  ⊙ {model_name}: Already analyzed (skip)")
        return result

    try:
        analysis, reasoning, raw = analyze_with_model(photo_path, model)
        save_vision_result(photo_id, model_name, analysis, reasoning, raw)
        result["status"] = "success"
        result["piece_type"] = analysis.piece_type
        result["glaze_type"] = analysis.glaze_type
        result["colors"] = analysis.primary_colors
        result["mood"] = analysis.mood
        print(f"  ✓ {model_name}: {analysis.piece_type} / {(analysis.glaze_type or 'unknown')[:30]}...")
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  ✗ {model_name}: Error: {e}")

    return result


# =============================================================================
# MAIN
# =============================================================================

def run_once(force: bool = False):
    """Run vision analysis once on all photos in To Post."""
    print("\n" + "="*60)
    print("STAGE 1: AUTO VISION ANALYSIS")
    print("="*60)

    # Clear export directory to avoid duplicate file issues from macOS Photos renaming
    if EXPORT_DIR.exists():
        shutil.rmtree(EXPORT_DIR)
        print("🧹 Cleared export directory")
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Get photos from To Post album
    print("\n📁 Scanning 'To Post' album...")
    media = get_media_from_album("To Post")

    if not media:
        print("No photos found in 'To Post' album.")
        return

    # Filter to images only (for now)
    images = [m for m in media if m.media_type == MediaType.PHOTO]
    videos = [m for m in media if m.media_type == MediaType.VIDEO]
    print(f"Found {len(images)} image(s), {len(videos)} video(s)\n")

    if not images:
        print("No images found (videos not supported yet).")
        return

    # Export all photos first (needed before parallel processing)
    print("📦 Exporting photos from album...")
    exported = []  # (item, photo_path) tuples
    for item in images:
        photo_path = export_media_by_id("To Post", item.id, str(EXPORT_DIR))
        if photo_path:
            exported.append((item, photo_path))
        else:
            print(f"  ✗ Could not export {item.filename}")

    if not exported:
        print("No photos exported successfully.")
        return

    # Build assignments: ALL models analyze ALL photos for union merge
    assignments = [
        (item, Path(path), model)
        for item, path in exported
        for model in MODELS
    ]

    print(f"\n🚀 Processing {len(exported)} photos across {len(MODELS)} models (all models × all photos)")

    # Process assignments sequentially to avoid DB contention from
    # caption_generator.py writing during analyze_photo() calls
    all_results = []
    for item, photo_path, model in assignments:
        result = process_photo(photo_path, model, force)
        all_results.append((item, result))

        # Copy analyzed photo to dashboard directory if successful
        if result["status"] == "success":
            PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
            dest = PHOTOS_DIR / photo_path.name
            if not dest.exists():
                shutil.copy2(photo_path, dest)
                print(f"  -> Copied to {dest}")

    # Summary
    print("\n" + "-"*60)
    print("SUMMARY")
    print("-"*60)

    print(f"Total photos: {len(exported)}")
    print(f"Total API calls: {len(assignments)} ({len(exported)} photos × {len(MODELS)} models)")
    for model in MODELS:
        assigned = sum(1 for _, _, m in assignments if m["name"] == model["name"])
        success = sum(1 for _, r in all_results if r["model"] == model["name"] and r["status"] == "success")
        skipped = sum(1 for _, r in all_results if r["model"] == model["name"] and r["status"] == "skipped")
        errors = sum(1 for _, r in all_results if r["model"] == model["name"] and r["status"] == "error")
        print(f"  {model['name']}: {assigned} assigned, {success} successful, {skipped} skipped, {errors} errors")
    print(f"\nNext step: Open http://localhost:8766/ to review and generate captions")


def watch_mode(interval: int = 60):
    """Watch for new photos and analyze automatically."""
    print(f"\n👀 Watch mode enabled (checking every {interval}s)")
    print("Press Ctrl+C to stop\n")

    while True:
        try:
            run_once(force=False)
            print(f"\n😴 Sleeping {interval}s...\n")
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n\nStopped.")
            break


def main():
    parser = argparse.ArgumentParser(description="Auto vision analysis for ceramics pipeline")
    parser.add_argument("--watch", action="store_true", help="Watch for new photos continuously")
    parser.add_argument("--force", action="store_true", help="Re-analyze all photos")
    parser.add_argument("--interval", type=int, default=60, help="Watch interval in seconds")

    args = parser.parse_args()

    # Initialize database
    init_db()
    migrate_db()

    if args.watch:
        watch_mode(args.interval)
    else:
        run_once(force=args.force)


if __name__ == "__main__":
    main()
