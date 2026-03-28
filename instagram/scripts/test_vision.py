#!/usr/bin/env python3
"""
Vision detection test - see raw LLM response without caption generation.

Usage:
    python scripts/test_vision.py --photo data/archive/cerafica_media/IMG_4782.jpg
    python scripts/test_vision.py --album "To Post" --compact
"""

import sys
import json
import base64
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from caption_generator import VISION_PROMPT_TEMPLATE, PhotoAnalysis, analyze_video
from photo_export import get_media_from_album, export_media_by_index, MediaType


def call_vision_api(photo_path: str, model: str, base_url: str) -> str:
    """Call Ollama/OpenRouter API and return raw response text."""
    # Read and encode image
    with open(photo_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode()

    # Detect cloud model (uses /api/chat endpoint)
    endpoint = "/api/chat" if ":cloud" in model else "/api/generate"

    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": VISION_PROMPT_TEMPLATE,
            "images": [image_b64]
        }],
        "stream": False
    }

    response = requests.post(f"{base_url}{endpoint}", json=payload)
    result = response.json()

    # Extract content based on endpoint type
    if ":cloud" in model:
        return result.get("message", {}).get("content", "")
    else:
        return result.get("response", "")


def parse_response(response_text: str) -> dict:
    """Parse JSON from LLM response."""
    import re
    json_match = re.search(r'\{[\s\S]*\}', response_text)
    if json_match:
        return json.loads(json_match.group())
    return {}


def test_photo(photo_path: str, model: str, base_url: str, compact: bool = False):
    """Test vision on single photo."""

    if not compact:
        print("\n" + "=" * 60)
        print(f"PHOTO: {photo_path}")
        print(f"MODEL: {model}")
        print("=" * 60)

    # Call API
    raw_response = call_vision_api(photo_path, model, base_url)

    if not compact:
        # Show raw response
        print("\n--- RAW LLM RESPONSE ---")
        print(raw_response)
        print("--- END RAW RESPONSE ---\n")

        # Show parsed
        parsed = parse_response(raw_response)
        print("--- PARSED JSON ---")
        print(json.dumps(parsed, indent=2))
        print("--- END PARSED ---\n")
    else:
        # Compact: one line summary
        parsed = parse_response(raw_response)
        piece = parsed.get("piece_type", "?")
        glaze = parsed.get("glaze_type", "?")
        color = parsed.get("color_appearance", "?")
        clay = parsed.get("clay_type", "?")
        surface_raw = parsed.get("surface_qualities", [])
        surface = ", ".join(surface_raw) if isinstance(surface_raw, list) else str(surface_raw)
        print(f"{Path(photo_path).name}: {piece} | {glaze} | {color} | {clay} | [{surface}]")


def test_video(video_path: str, compact: bool = False):
    """Test video analysis (uses multi-frame extraction)."""
    if not compact:
        print("\n" + "=" * 60)
        print(f"VIDEO: {video_path}")
        print("=" * 60)

    # Run video analysis
    result = analyze_video(video_path, use_ai=True)

    if not compact:
        print("\n--- VIDEO ANALYSIS ---")
        print(f"  content_type: {result.content_type.value}")
        print(f"  video_type: {result.video_type}")
        print(f"  duration: {result.duration_seconds:.1f}s")
        print(f"  aspect_ratio: {result.aspect_ratio_category}")
        print(f"  primary_colors: {result.primary_colors}")
        print(f"  activity: {result.activity}")
        print(f"  mood: {result.mood}")
        print(f"  suggested_hook: {result.suggested_hook}")
        print(f"  is_reel_suitable: {result.is_reel_suitable}")
        if result.duration_warning:
            print(f"  duration_warning: {result.duration_warning}")
        print("--- END ANALYSIS ---\n")
    else:
        # Compact: one line summary
        reel_status = "REEL" if result.is_reel_suitable else "FEED"
        print(f"{Path(video_path).name}: {result.video_type} | {result.activity} | {result.duration_seconds:.1f}s | {reel_status}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Test vision detection pipeline")
    parser.add_argument("--photo", help="Path to single photo")
    parser.add_argument("--video", help="Path to single video")
    parser.add_argument("--album", help="Album name to test")
    parser.add_argument("--model", default="kimi-k2.5:cloud", help="Model to use")
    parser.add_argument("--base-url", default="http://localhost:11434", help="API base URL")
    parser.add_argument("--show-prompt", action="store_true", help="Print the full prompt template")
    parser.add_argument("--compact", action="store_true", help="Compact one-line output")
    parser.add_argument("--videos-only", action="store_true", help="Test only videos in album")
    args = parser.parse_args()

    if args.show_prompt:
        print(VISION_PROMPT_TEMPLATE)
        return

    if args.photo:
        test_photo(args.photo, args.model, args.base_url, args.compact)

    elif args.video:
        test_video(args.video, args.compact)

    elif args.album:
        import tempfile
        media = get_media_from_album(args.album)
        print(f"Found {len(media)} items in '{args.album}'\n")
        with tempfile.TemporaryDirectory() as tmpdir:
            for i, item in enumerate(media):
                if args.videos_only:
                    if item.media_type in (MediaType.VIDEO, MediaType.REEL, MediaType.STORY):
                        exported = export_media_by_index(args.album, i, tmpdir)
                        if exported:
                            test_video(exported, args.compact)
                elif item.media_type == MediaType.PHOTO:
                    # Export and test photo
                    exported = export_media_by_index(args.album, i, tmpdir)
                    if exported:
                        test_photo(exported, args.model, args.base_url, args.compact)
                elif item.media_type in (MediaType.VIDEO, MediaType.REEL, MediaType.STORY):
                    # Export and test video
                    exported = export_media_by_index(args.album, i, tmpdir)
                    if exported:
                        test_video(exported, args.compact)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
