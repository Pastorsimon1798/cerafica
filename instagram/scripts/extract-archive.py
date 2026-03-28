#!/usr/bin/env python3
"""
Extract Instagram Archive for Ceramics Workspace

Extracts all posts from a public Instagram account and saves:
1. Full metadata to JSON archive
2. Media files (images/videos) to local folder

Usage:
    python extract-archive.py [username]

Default username: cerafica_design
"""

import sys
import time
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

import instaloader
from instaloader_utils import (
    get_instaloader_instance,
    get_media_dir,
    get_archive_path,
    post_to_dict,
    save_archive,
    update_sync_timestamp,
    print_progress,
)


def extract_archive(username: str = "cerafica_design") -> dict:
    """
    Extract all posts from an Instagram account.

    Args:
        username: Instagram username (without @)

    Returns:
        Dictionary with extraction results
    """
    print(f"\n{'='*60}")
    print(f"Instagram Archive Extraction")
    print(f"Target: @{username}")
    print(f"{'='*60}\n")

    # Initialize Instaloader
    L = get_instaloader_instance()

    # Create output directories
    media_dir = get_media_dir()
    media_dir.mkdir(parents=True, exist_ok=True)

    # Get profile
    print(f"Loading profile @{username}...")
    try:
        profile = instaloader.Profile.from_username(L.context, username)
    except instaloader.ProfileNotExistsException:
        print(f"Error: Profile @{username} does not exist.")
        sys.exit(1)
    except instaloader.LoginRequiredException:
        print(f"Error: Profile @{username} requires login to view.")
        sys.exit(1)

    # Get total post count
    total_posts = profile.mediacount
    print(f"Found {total_posts} posts to extract.\n")

    # Prepare archive structure
    archive = {
        "metadata": {
            "username": username,
            "extracted_at": datetime.now().isoformat(),
            "total_posts": total_posts,
            "profile_info": {
                "full_name": profile.full_name,
                "biography": profile.biography,
                "followers": profile.followers,
                "followees": profile.followees,
                "is_private": profile.is_private,
                "external_url": str(profile.external_url) if profile.external_url else None,
            },
        },
        "posts": [],
    }

    # Extract posts
    print("Extracting posts...")
    posts = profile.get_posts()

    extracted_count = 0
    failed_count = 0

    for post in posts:
        extracted_count += 1
        print_progress(extracted_count, total_posts, "Extracting")

        try:
            # Convert post to dict
            post_data = post_to_dict(post)

            # Download media
            try:
                L.download_post(post, target=media_dir)
            except Exception as e:
                print(f"\n  Warning: Could not download media for {post.shortcode}: {e}")

            # Add to archive
            archive["posts"].append(post_data)

            # Rate limiting - be nice to Instagram
            time.sleep(2)

        except Exception as e:
            failed_count += 1
            print(f"\n  Error extracting post {post.shortcode}: {e}")
            continue

    print(f"\n\nExtraction complete!")
    print(f"  - Successfully extracted: {extracted_count - failed_count}")
    print(f"  - Failed: {failed_count}")

    # Sort posts by date (newest first)
    archive["posts"].sort(key=lambda x: x["date"], reverse=True)

    # Save archive
    save_archive(archive)
    print(f"\nArchive saved to: {get_archive_path()}")
    print(f"Media saved to: {media_dir}")

    # Update sync timestamp
    update_sync_timestamp()

    return archive


def main():
    """Main entry point."""
    username = sys.argv[1] if len(sys.argv) > 1 else "cerafica_design"

    print("\n" + "=" * 60)
    print("CERAMICS INSTAGRAM ARCHIVE EXTRACTOR")
    print("=" * 60)
    print("\nThis script will extract all posts from the specified account.")
    print("For large accounts, this may take a while.")
    print("\nPress Ctrl+C to cancel at any time.\n")

    try:
        archive = extract_archive(username)

        # Print summary
        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Username: @{archive['metadata']['username']}")
        print(f"Total posts: {len(archive['posts'])}")
        print(f"Followers: {archive['metadata']['profile_info']['followers']:,}")

        if archive["posts"]:
            # Calculate totals
            total_likes = sum(p["likes"] for p in archive["posts"])
            total_comments = sum(p["comments"] for p in archive["posts"])
            avg_likes = total_likes / len(archive["posts"])

            print(f"Total likes: {total_likes:,}")
            print(f"Total comments: {total_comments:,}")
            print(f"Average likes per post: {avg_likes:.0f}")

            # Date range
            dates = [p["date"] for p in archive["posts"]]
            print(f"Date range: {min(dates)[:10]} to {max(dates)[:10]}")

        print("\n✓ Extraction complete!")

    except KeyboardInterrupt:
        print("\n\nExtraction cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
