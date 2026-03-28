"""
Shared utilities for Instagram extraction and analysis scripts.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import instaloader


def get_workspace_root() -> Path:
    """Get the workspace root directory."""
    return Path(__file__).parent.parent.parent.parent


def get_data_dir() -> Path:
    """Get the data directory."""
    return get_workspace_root() / "data"


def get_archive_path() -> Path:
    """Get the archive JSON file path."""
    return get_data_dir() / "archive" / "cerafica_archive.json"


def get_media_dir() -> Path:
    """Get the media directory."""
    return get_data_dir() / "archive" / "cerafica_media"


def get_sync_timestamp_path() -> Path:
    """Get the last sync timestamp file path."""
    return get_data_dir() / "sync" / "last_sync.txt"


def load_archive() -> dict:
    """Load the archive JSON file."""
    archive_path = get_archive_path()
    if not archive_path.exists():
        return {"posts": [], "metadata": {}}

    with open(archive_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_archive(archive: dict) -> None:
    """Save the archive JSON file."""
    archive_path = get_archive_path()
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump(archive, f, indent=2, ensure_ascii=False, default=str)


def update_sync_timestamp() -> None:
    """Update the last sync timestamp to now."""
    sync_path = get_sync_timestamp_path()
    sync_path.parent.mkdir(parents=True, exist_ok=True)

    with open(sync_path, "w") as f:
        f.write(datetime.now().isoformat())


def get_last_sync_timestamp() -> Optional[datetime]:
    """Get the last sync timestamp."""
    sync_path = get_sync_timestamp_path()
    if not sync_path.exists():
        return None

    with open(sync_path, "r") as f:
        timestamp_str = f.read().strip()

    try:
        return datetime.fromisoformat(timestamp_str)
    except ValueError:
        return None


def extract_hashtags_from_caption(caption: Optional[str]) -> list[str]:
    """Extract hashtags from a caption."""
    if not caption:
        return []

    hashtags = []
    for word in caption.split():
        if word.startswith("#"):
            # Clean the hashtag (remove punctuation at end)
            clean_tag = word.strip(".,!?;:")
            if len(clean_tag) > 1:
                hashtags.append(clean_tag.lower())

    return hashtags


def post_to_dict(post: instaloader.Post) -> dict:
    """Convert an Instaloader Post object to a dictionary."""
    return {
        "shortcode": post.shortcode,
        "mediaid": post.mediaid,
        "url": f"https://www.instagram.com/p/{post.shortcode}/",
        "caption": post.caption,
        "hashtags": extract_hashtags_from_caption(post.caption),
        "date": post.date_local.isoformat(),
        "likes": post.likes,
        "comments": post.comments,
        "is_video": post.is_video,
        "video_url": str(post.video_url) if post.is_video else None,
        "image_url": str(post.url),
        "caption_hashtags": post.caption_hashtags,
        "caption_mentions": post.caption_mentions,
        "location": post.location,
        "typename": post.typename,
        "mediacount": post.mediacount if hasattr(post, "mediacount") else 1,
    }


def format_number(n: int) -> str:
    """Format a number with commas."""
    return f"{n:,}"


def calculate_engagement_rate(likes: int, comments: int, followers: Optional[int] = None) -> float:
    """Calculate engagement rate."""
    if followers and followers > 0:
        return ((likes + comments) / followers) * 100
    return likes + comments  # Return raw engagement if no follower count


def print_progress(current: int, total: int, description: str = "Processing") -> None:
    """Print a progress message."""
    percent = (current / total) * 100 if total > 0 else 0
    print(f"\r{description}: {current}/{total} ({percent:.1f}%)", end="", flush=True)


def get_instaloader_instance() -> instaloader.Instaloader:
    """Get an Instaloader instance with sensible defaults."""
    L = instaloader.Instaloader(
        download_videos=True,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )
    return L
