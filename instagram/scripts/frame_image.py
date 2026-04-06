#!/usr/bin/env python3
"""
CLI tool for generating framed images.

Usage:
    python scripts/frame_image.py --test IMG_4759.jpg
    python scripts/frame_image.py --photo IMG_4759.jpg --planet "Pallth-7" --sector "Obsidian Cluster"
    python scripts/frame_image.py --batch  # Process all photos in To Post album

The --test flag outputs to output/framed/test/ for quick review.
"""

import argparse
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from frame_generator import (
    PlanetaryFrameGenerator,
    MinimalFrameGenerator,
    generate_planetary_frame,
    generate_minimal_frame,
    FRAMED_OUTPUT_DIR,
    OUTPUT_WIDTH,
    OUTPUT_HEIGHT
)

WEBSITE_OUTPUT_DIR = Path(__file__).parent.parent.parent / "website" / "images" / "products"
from photo_export import get_media_from_album, export_media_by_index, get_temp_export_dir, import_photo_to_album, create_albums

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"


def get_planet_data_from_db(photo_filename: str) -> dict:
    """Get planet data from series_pieces table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Look for matching photo (handle extensions)
    base_name = Path(photo_filename).stem

    cursor.execute("""
        SELECT planet_name, orbital_data, surface_geology, formation_history, order_index
        FROM series_pieces
        WHERE photo LIKE ?
        LIMIT 1
    """, (f"{base_name}%",))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "planet_name": row["planet_name"],
            "sector": row["orbital_data"],  # orbital_data is used as sector
            "surface_geology": row["surface_geology"],
            "log_number": row["order_index"],
            "lore": row["formation_history"]
        }

    return None


def get_series_info_for_photo(photo_filename: str) -> dict | None:
    """
    Get series info including frame_style for a photo.

    Returns dict with 'series_name', 'frame_style', 'description' or None.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    base_name = Path(photo_filename).stem

    cursor.execute("""
        SELECT s.name, s.frame_style, s.description
        FROM series s
        JOIN series_pieces sp ON s.id = sp.series_id
        WHERE sp.photo LIKE ?
        LIMIT 1
    """, (f"{base_name}%",))

    row = cursor.fetchone()
    conn.close()

    if row:
        return {
            "series_name": row["name"],
            "frame_style": row["frame_style"] or "planetary",
            "description": row["description"],
        }

    return None


def get_vision_analysis(photo_filename: str) -> dict | None:
    """Get vision analysis from vision_results table."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    base_name = Path(photo_filename).stem

    # Get photo_id from photos table
    cursor.execute("SELECT id FROM photos WHERE filename LIKE ?", (f"{base_name}%",))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    photo_id = row["id"]

    # Get vision results (prefer Kimi - better surface detection)
    cursor.execute("""
        SELECT piece_type, primary_colors, secondary_colors, surface_qualities,
               mood, technique, form_attributes, color_appearance, firing_state,
               clay_type, hypotheses, vision_reasoning
        FROM vision_results
        WHERE photo_id = ?
        ORDER BY CASE WHEN model = 'Kimi' THEN 0 WHEN model = 'Kimi K2.5' THEN 1 ELSE 2 END,
                 (color_appearance IS NOT NULL) DESC,
                 created_at DESC
        LIMIT 1
    """, (photo_id,))

    row = cursor.fetchone()
    conn.close()

    if not row:
        return None

    result = {
        "primary_colors": json.loads(row["primary_colors"]) if row["primary_colors"] else [],
        "secondary_colors": json.loads(row["secondary_colors"]) if row["secondary_colors"] else [],
        "surface_qualities": json.loads(row["surface_qualities"]) if row["surface_qualities"] else [],
    }

    # Extract lighting direction if available
    if row["hypotheses"]:
        hypotheses = json.loads(row["hypotheses"]) if isinstance(row["hypotheses"], str) else row["hypotheses"]
        if hypotheses:
            import re
            hypotheses_text = " ".join(str(h) for h in hypotheses[:3]).lower()
            # Detect lighting direction from vision hypotheses
            if "top" in hypotheses_text or "overhead" in hypotheses_text or "above" in hypotheses_text:
                result["light_direction"] = "top"
            elif "side" in hypotheses_text or "raking" in hypotheses_text or "lateral" in hypotheses_text:
                result["light_direction"] = "side"
            elif "back" in hypotheses_text or "behind" in hypotheses_text:
                result["light_direction"] = "bottom"
            else:
                result["light_direction"] = None

    # Add optional fields that may not exist in older records
    for field in ["piece_type", "mood", "technique", "color_appearance", "firing_state",
                  "clay_type", "vision_reasoning"]:
        val = row[field]
        if field in ("hypotheses", "form_attributes") and val:
            val = json.loads(val)
        result[field] = val

    return result


def frame_single_photo(photo_path: str, planet_data: dict = None, test_mode: bool = False,
                        import_to_photos: bool = False, output_name: str = None,
                        website: bool = False) -> str:
    """
    Generate a framed image for a single photo.

    Args:
        photo_path: Path to the photo file
        planet_data: Optional planet data dict. If None, will try to load from DB.
        test_mode: If True, save to test directory
        import_to_photos: If True, import framed image to "Ready to Post" Photos album
        output_name: Optional filename override for the saved output (without extension).
                     Use when photo_path is a temp file and the real filename should be preserved.
        website: If True, generate website product frame (no HUD chrome).

    Returns:
        Path to saved framed image
    """
    # Try to get planet data from DB if not provided
    if planet_data is None:
        planet_data = get_planet_data_from_db(Path(photo_path).name)

    # Use default data if still None
    if planet_data is None:
        photo_name = Path(photo_path).stem
        planet_data = {
            "planet_name": f"Planet-{photo_name}",
            "sector": "Unknown Sector",
            "surface_geology": "Uncharted terrain",
            "log_number": hash(photo_name) % 999 + 1
        }
        print("  No planet data found, using defaults")

    # Derive chemistry from vision analysis if not already present
    if "chemistry" not in planet_data or not planet_data.get("chemistry"):
        vision = get_vision_analysis(Path(photo_path).name)
        if vision:
            from frame_generator import (
                colors_to_chemistry_string, surface_to_geology_string,
                hypotheses_to_chemistry_string, extract_chemistry_from_hypotheses
            )
            # Try hypotheses first for rich chemistry language
            chemistry = hypotheses_to_chemistry_string(vision.get("hypotheses"))
            if chemistry:
                planet_data["chemistry"] = chemistry
                print(f"  Chemistry (from hypotheses): {chemistry}")
            else:
                # Fall back to color→formula map
                chemistry = colors_to_chemistry_string(vision["primary_colors"])
                if chemistry:
                    planet_data["chemistry"] = chemistry
                    print(f"  Chemistry (from colors): {chemistry}")
            # Enhance surface_geology if generic
            if planet_data.get("surface_geology") in ["Uncharted terrain", None]:
                geology = surface_to_geology_string(vision["surface_qualities"])
                if geology:
                    planet_data["surface_geology"] = geology

            # Map additional vision data to worldbuilding fields
            if vision.get("surface_qualities"):
                planet_data["surface_qualities"] = ", ".join(vision["surface_qualities"])
            if vision.get("primary_colors"):
                planet_data["primary_colors"] = vision["primary_colors"]
            if vision.get("secondary_colors"):
                planet_data["secondary_colors"] = vision["secondary_colors"]
            if vision.get("mood"):
                planet_data["mood"] = vision["mood"]
            if vision.get("piece_type"):
                planet_data["classification"] = vision["piece_type"]
            if vision.get("technique"):
                clay = vision.get("clay_type", "stoneware")
                clay_label = clay.replace("_", " ").title() if clay else "stoneware"
                planet_data["origin"] = f"{vision['technique'].replace('-', '-').title()}, {clay_label} substrate"
            if vision.get("color_appearance"):
                planet_data["spectral"] = vision["color_appearance"][:80]
            if vision.get("hypotheses"):
                anomalies = extract_chemistry_from_hypotheses(vision["hypotheses"])
                if anomalies:
                    planet_data["anomalies"] = anomalies
            if vision.get("form_attributes"):
                planet_data["form_attributes"] = ", ".join(vision["form_attributes"]) if isinstance(vision["form_attributes"], list) else vision["form_attributes"]
            if vision.get("firing_state"):
                planet_data["firing_state"] = vision["firing_state"]
            if vision.get("clay_type"):
                planet_data["clay_type"] = vision["clay_type"]
            if vision.get("light_direction"):
                planet_data["light_direction"] = vision["light_direction"]

    # Determine frame style from series
    series_info = get_series_info_for_photo(Path(photo_path).name)
    frame_style = series_info["frame_style"] if series_info else "planetary"
    series_name = series_info["series_name"] if series_info else ""

    # Determine the output stem: use output_name if provided, else derive from photo_path
    output_stem = Path(output_name).stem if output_name else Path(photo_path).stem

    # Generate frame using the appropriate generator
    saved_path = None
    if website:
        # Website mode: clean product frame, no HUD chrome
        generator = PlanetaryFrameGenerator()
        framed = generator.generate_website_frame(photo_path, planet_data)

        if test_mode:
            test_dir = FRAMED_OUTPUT_DIR / "test"
            test_dir.mkdir(parents=True, exist_ok=True)
            output_path = test_dir / f"{output_stem}_website.jpg"
            framed.save(output_path, "JPEG", quality=98, subsampling=0)
            saved_path = str(output_path)
        else:
            # Output to website/images/products/ using planet_name as filename
            WEBSITE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            planet_name = planet_data.get("planet_name", output_stem)
            safe_name = planet_name.lower().replace(" ", "-")
            output_path = WEBSITE_OUTPUT_DIR / f"{safe_name}.jpg"
            framed.save(output_path, "JPEG", quality=98, subsampling=0)
            saved_path = str(output_path)

        # No Photos import for website frames
    elif frame_style == "minimal":
        minimal_data = {
            "series_name": series_name,
            "piece_description": planet_data.get("surface_geology", ""),
        }
        if test_mode:
            generator = MinimalFrameGenerator()
            framed = generator.generate_frame(photo_path, minimal_data)
            test_dir = FRAMED_OUTPUT_DIR / "test"
            test_dir.mkdir(parents=True, exist_ok=True)
            output_path = test_dir / f"{output_stem}_minimal.jpg"
            framed.save(output_path, "JPEG", quality=98, subsampling=0)
            saved_path = str(output_path)
        else:
            _, saved_path = generate_minimal_frame(photo_path, minimal_data, save=True, output_name=output_stem)
    else:
        # Default: planetary
        if test_mode:
            generator = PlanetaryFrameGenerator()
            framed = generator.generate_frame(photo_path, planet_data)
            test_dir = FRAMED_OUTPUT_DIR / "test"
            test_dir.mkdir(parents=True, exist_ok=True)
            output_path = test_dir / f"{output_stem}_planetary.jpg"
            framed.save(output_path, "JPEG", quality=98, subsampling=0)
            saved_path = str(output_path)
        else:
            _, saved_path = generate_planetary_frame(photo_path, planet_data, save=True, output_name=output_stem)

    # Import to Photos app if requested (not for website frames)
    if not website:
        if import_to_photos and saved_path and not test_mode:
            create_albums(["Ready to Post"])
            if import_photo_to_album(saved_path, "Ready to Post"):
                print("  -> Imported to 'Ready to Post' album")
            else:
                print("  -> Failed to import to 'Ready to Post' album")

        # Always import to Framed Series album (non-test mode)
        if saved_path and not test_mode:
            create_albums(["Framed Series"])
            if import_photo_to_album(saved_path, "Framed Series"):
                print("  -> Imported to 'Framed Series' album")

    return saved_path


def frame_from_album(album_name: str = "To Post", index: int = 0, planet_data: dict = None, website: bool = False) -> str:
    """
    Export and frame a photo from a Photos album.

    Args:
        album_name: Name of the album
        index: Zero-based index of photo in album
        planet_data: Optional planet data dict
        website: If True, generate website product frame

    Returns:
        Path to saved framed image
    """
    # Get media from album
    media_items = get_media_from_album(album_name)
    if not media_items:
        print(f"No media found in album '{album_name}'")
        return None

    if index >= len(media_items):
        print(f"Index {index} out of range (album has {len(media_items)} items)")
        return None

    item = media_items[index]
    print(f"Framing: {item.filename}")

    # Export to temp directory
    temp_dir = get_temp_export_dir()
    exported_path = export_media_by_index(album_name, index, temp_dir)

    if not exported_path:
        print(f"Failed to export {item.filename}")
        return None

    # Frame it
    return frame_single_photo(exported_path, planet_data, website=website)


def batch_frame(album_name: str = "To Post", dry_run: bool = False, website: bool = False) -> list:
    """
    Frame all photos in an album that have planet data.

    Args:
        album_name: Name of the album
        dry_run: If True, don't actually generate frames
        website: If True, generate website product frames

    Returns:
        List of paths to framed images
    """
    media_items = get_media_from_album(album_name)
    if not media_items:
        print(f"No media found in album '{album_name}'")
        return []

    # Filter to photos only (not videos)
    from photo_export import MediaType
    photos = [m for m in media_items if m.media_type == MediaType.PHOTO]

    print(f"Found {len(photos)} photos in '{album_name}'")

    results = []
    temp_dir = get_temp_export_dir()

    for i, photo in enumerate(photos):
        print(f"\n[{i+1}/{len(photos)}] {photo.filename}")

        # Check if planet data exists
        planet_data = get_planet_data_from_db(photo.filename)
        if planet_data is None:
            print("  Skipping - no planet data in database")
            continue

        print(f"  Planet: {planet_data['planet_name']}")

        if dry_run:
            print(f"  [DRY RUN] Would frame with: {planet_data}")
            results.append(None)
            continue

        # Export and frame
        exported = export_media_by_index(album_name, i, temp_dir)
        if not exported:
            print("  Failed to export")
            continue

        framed_path = frame_single_photo(exported, planet_data, output_name=photo.filename, website=website)
        if framed_path:
            print(f"  Saved: {framed_path}")
            results.append(framed_path)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Generate framed images for Instagram posts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test frame with a specific photo
  python scripts/frame_image.py --test IMG_4759.jpg

  # Frame with custom planet data
  python scripts/frame_image.py --photo IMG_4759.jpg --planet "Pallth-7" --sector "Obsidian Cluster"

  # Frame all photos in album with planet data
  python scripts/frame_image.py --batch

  # Dry run batch (see what would be framed)
  python scripts/frame_image.py --batch --dry-run

  # Website product frame (no HUD chrome)
  python scripts/frame_image.py --website --test IMG_4759.jpg
  python scripts/frame_image.py --website --photo IMG_4759.jpg
  python scripts/frame_image.py --website --batch
"""
    )

    # Photo source options
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--test", metavar="PHOTO",
                              help="Test frame a photo (outputs to test directory)")
    source_group.add_argument("--photo", metavar="PHOTO",
                              help="Path to photo file to frame")
    source_group.add_argument("--album", metavar="ALBUM",
                              help="Frame first photo from album (default: To Post)")
    source_group.add_argument("--batch", action="store_true",
                              help="Frame all photos in album with planet data")

    # Planet data options (for --photo and --album)
    parser.add_argument("--planet", metavar="NAME",
                        help="Planet name (e.g., 'Pallth-7')")
    parser.add_argument("--sector", metavar="NAME",
                        help="Sector name")
    parser.add_argument("--surface", metavar="DESC",
                        help="Surface geology description")
    parser.add_argument("--log", type=int, metavar="NUM",
                        help="Log number")

    # Batch options
    parser.add_argument("--dry-run", action="store_true",
                        help="Dry run for batch mode (don't actually generate)")
    parser.add_argument("--import", dest="import_photos", action="store_true",
                        help="Import framed image to 'Ready to Post' Photos album")

    # Output mode
    parser.add_argument("--website", action="store_true",
                        help="Generate website product frame (pottery + space bg + zoom, no HUD chrome)")

    args = parser.parse_args()

    # Build planet data if provided
    planet_data = None
    if args.planet or args.sector or args.surface or args.log:
        planet_data = {
            "planet_name": args.planet or "Unknown",
            "sector": args.sector or "Unknown Sector",
            "surface_geology": args.surface or "Unknown terrain",
            "log_number": args.log or 1
        }

    # Execute based on mode
    result = None

    if args.test:
        # Find the test photo
        test_path = Path(args.test)
        if not test_path.exists():
            # Try common locations
            search_dirs = [
                Path(__file__).parent.parent.parent / "instagram" / "ab_test_photos",
                Path(__file__).parent.parent.parent / "instagram" / "vision_exports",
                Path.cwd()
            ]
            for search_dir in search_dirs:
                if search_dir.exists():
                    for ext in ["", ".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG"]:
                        candidate = search_dir / f"{test_path.stem}{ext}"
                        if candidate.exists():
                            test_path = candidate
                            break
                    if test_path.exists():
                        break

        if not test_path.exists():
            print(f"Error: Could not find photo '{args.test}'")
            sys.exit(1)

        print(f"Test framing: {test_path}")
        result = frame_single_photo(str(test_path), planet_data, test_mode=True, website=args.website)
        print(f"\nTest output: {result}")

    elif args.photo:
        photo_path = Path(args.photo)
        if not photo_path.exists():
            print(f"Error: Photo not found: {args.photo}")
            sys.exit(1)

        result = frame_single_photo(str(photo_path), planet_data, import_to_photos=args.import_photos, website=args.website)
        print(f"\nFramed image: {result}")

    elif args.album is not None or (hasattr(args, 'album') and args.album is None and not args.batch):
        album = args.album or "To Post"
        print(f"Framing first photo from album: {album}")
        result = frame_from_album(album, 0, planet_data, website=args.website)
        if result and args.import_photos:
            create_albums(["Ready to Post"])
            if import_photo_to_album(result, "Ready to Post"):
                print("  -> Imported to 'Ready to Post' album")
        if result:
            print(f"\nFramed image: {result}")

    elif args.batch:
        print("Batch framing photos with planet data...")
        results = batch_frame(dry_run=args.dry_run, website=args.website)
        successful = [r for r in results if r]
        print(f"\nFramed {len(successful)} photos")
        for r in successful:
            print(f"  - {r}")

    if result:
        print(f"\nOutput dimensions: {OUTPUT_WIDTH}x{OUTPUT_HEIGHT} (4:5 Instagram portrait)")


if __name__ == "__main__":
    main()
