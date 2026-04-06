#!/usr/bin/env python3
"""
Process all photos in "To Post" album with Kimi vision.
Updates the human-door dashboard with results.
"""

import sys
import json
import os
from pathlib import Path
from datetime import datetime
from dataclasses import asdict

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from photo_export import get_media_from_album, export_media_by_index, get_temp_export_dir, MediaType
from caption_generator import analyze_photo, generate_caption, select_hashtags, PhotoAnalysis

def main():
    # Get all media from "To Post" album
    print("Getting photos from 'To Post' album...")
    media = get_media_from_album('To Post')
    photos = [(i, m) for i, m in enumerate(media) if m.media_type == MediaType.PHOTO]

    print(f"Found {len(photos)} photos to process\n")

    results = []
    temp_dir = get_temp_export_dir()

    for count, (media_index, photo) in enumerate(photos):
        print(f"[{count+1}/{len(photos)}] Processing {photo.filename}...")

        # Export photo using its index in the FULL media list
        export_path = export_media_by_index('To Post', media_index, temp_dir)
        if not export_path:
            print(f"  ERROR: Could not export {photo.filename}")
            continue

        print(f"  Exported to: {export_path}")

        # Run vision analysis with Kimi
        print("  Running vision analysis...")
        vision_result = analyze_photo(export_path)

        if not vision_result:
            print("  ERROR: Vision analysis failed")
            continue

        print(f"  Vision: {vision_result.piece_type}, {vision_result.form_attributes}")

        # Generate caption
        print("  Generating caption...")
        caption_result = generate_caption(vision_result)

        # Generate hashtags (caption already has some, but get more)
        hashtags = select_hashtags(vision_result)

        # Build result object
        result = {
            "photo": photo.filename,
            "model": "Kimi K2.5",
            "vision": asdict(vision_result),
            "captions": {
                "hook": caption_result.hook,
                "body": caption_result.body,
                "cta": caption_result.cta,
                "full_caption": caption_result.full_caption,
                "hashtags": hashtags
            }
        }

        # Convert enums to strings for JSON serialization
        result["vision"]["content_type"] = vision_result.content_type.value if hasattr(vision_result.content_type, 'value') else str(vision_result.content_type)
        result["vision"]["mood"] = vision_result.mood.value if hasattr(vision_result.mood, 'value') else str(vision_result.mood) if vision_result.mood else "organic"

        results.append(result)
        print("  Done!\n")

    # Save to dashboard
    test_data = {
        "total_tests": len(results),
        "generated_at": datetime.now().isoformat(),
        "model": "Kimi K2.5",
        "results": results
    }

    dashboard_path = Path(__file__).parent.parent.parent / "tools" / "feedback" / "test_data.json"
    with open(dashboard_path, "w") as f:
        json.dump(test_data, f, indent=2)

    print(f"\n{'='*50}")
    print(f"Processed {len(results)}/{len(photos)} photos")
    print(f"Results saved to: {dashboard_path}")
    print("Refresh http://localhost:8766/pipeline to see updates")

if __name__ == "__main__":
    main()
