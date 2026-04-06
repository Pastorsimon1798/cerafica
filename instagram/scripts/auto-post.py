#!/usr/bin/env python3
"""
Instagram Auto-Post Script

Main orchestration script that runs weekly to:
1. Get photos from "To Post" album in Photos app
2. Export photos to temp folder
3. Generate captions using AI
4. Schedule posts via Meta Business Suite
5. Move photos to "Posted" album
6. Generate report

Usage:
    python auto-post.py           # Run normal workflow
    python auto-post.py --test    # Run in test mode (dry run)
    python auto-post.py --status  # Show pipeline status
    python auto-post.py --cron-test  # Verify cron setup
"""

import os
import sys
import json
import sqlite3
import argparse
import dataclasses
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))
# Add scripts dir for sibling imports (frame_image)
sys.path.insert(0, str(Path(__file__).parent))

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"

from lib.photo_export import (
    create_albums,
    get_photos_from_album,
    get_media_from_album,
    export_photo_by_index,
    export_media_by_index,
    move_photo_by_index,
    get_photo_count,
    get_temp_export_dir,
    clear_temp_exports,
    ensure_photos_app_running,
    is_video_file,
    get_video_info,
    get_aspect_ratio_category,
    MediaType,
    MediaInfo,
    MediaGroup,
)

from lib.caption_generator import (
    analyze_photo,
    analyze_video,
    analyze_carousel,
    generate_caption,
    generate_caption_for_carousel,
    PhotoAnalysis,
    VideoAnalysis,
    CarouselAnalysis,
    ContentType,
)

from lib.instagram_scheduler import (
    get_posting_schedule,
)

from frame_image import frame_single_photo, get_planet_data_from_db  # sibling script


def get_framed_output_dir() -> Path:
    """Get the framed output directory (videos and photos)."""
    return get_workspace_root() / "output" / "framed"


def collect_from_output_dir() -> list[MediaInfo]:
    """
    Collect framed media from output/framed/ directory.

    Scans:
    - output/framed/video/ for .mp4 files (framed videos)
    - output/framed/ dated subdirs for .jpg/.png files (framed photos)

    Returns:
        List of MediaInfo objects ready for processing
    """
    framed_dir = get_framed_output_dir()
    media_items = []

    # Collect framed videos
    video_dir = framed_dir / "video"
    if video_dir.exists():
        for path in sorted(video_dir.glob("*.mp4")):
            # Get video metadata via ffprobe
            video_info = get_video_info(str(path))
            width = video_info.get("width", 0)
            height = video_info.get("height", 0)
            duration = video_info.get("duration", 0)
            aspect_ratio = get_aspect_ratio_category(width, height) if width and height else "vertical"

            media_items.append(MediaInfo(
                id=f"output_{path.stem}",
                filename=path.name,
                date=datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                width=width,
                height=height,
                album="output/framed/video",
                media_type=MediaType.VIDEO,
                duration=duration,
                aspect_ratio=aspect_ratio,
                # Store absolute path for direct use (no export needed)
            ))
            # Attach file path for direct access
            media_items[-1]._file_path = str(path)

    # Collect framed photos from dated subdirs
    for subdir in sorted(framed_dir.iterdir()):
        if not subdir.is_dir() or subdir.name in ("video", ".DS_Store"):
            continue
        for path in sorted(subdir.glob("*.jpg")) + sorted(subdir.glob("*.png")):
            from PIL import Image
            try:
                with Image.open(path) as img:
                    width, height = img.size
            except Exception:
                width, height = 0, 0

            media_items.append(MediaInfo(
                id=f"output_{path.stem}",
                filename=path.name,
                date=datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                width=width,
                height=height,
                album=f"output/framed/{subdir.name}",
                media_type=MediaType.PHOTO,
                duration=0.0,
                aspect_ratio=get_aspect_ratio_category(width, height) if width and height else "horizontal",
            ))
            media_items[-1]._file_path = str(path)

    return media_items


def get_workspace_root() -> Path:
    """Get the workspace root directory."""
    return Path(__file__).parent.parent.parent


def get_logs_dir() -> Path:
    """Get the logs directory."""
    logs_dir = get_workspace_root() / "instagram" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_output_dir() -> Path:
    """Get the posting packs output directory."""
    output_dir = get_workspace_root() / "instagram" / "posting-packs"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_reports_dir() -> Path:
    """Get the reports output directory."""
    reports_dir = get_workspace_root() / "instagram" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def log(message: str, level: str = "INFO") -> None:
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [{level}] {message}")

    # Also write to log file
    log_file = get_logs_dir() / "auto-post.log"
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] [{level}] {message}\n")


def _save_caption_to_db(filename: str, caption) -> None:
    """Persist a generated caption to feedback.db caption_results table."""
    conn = sqlite3.connect(str(DB_PATH))
    try:
        c = conn.cursor()

        # Ensure photo exists in photos table
        c.execute('INSERT OR IGNORE INTO photos (filename) VALUES (?)', (filename,))
        c.execute('SELECT id FROM photos WHERE filename = ?', (filename,))
        row = c.fetchone()
        if not row:
            return
        photo_id = row[0]

        # Upsert caption (use 'pipeline' as model since it's the main pipeline)
        c.execute('''
            INSERT INTO caption_results (photo_id, model, hook, body, cta, full_caption, alt_text)
            VALUES (?, 'pipeline', ?, ?, ?, ?, ?)
            ON CONFLICT(photo_id, model) DO UPDATE SET
                hook = excluded.hook,
                body = excluded.body,
                cta = excluded.cta,
                full_caption = excluded.full_caption,
                alt_text = excluded.alt_text
        ''', (photo_id, caption.hook, caption.body, caption.cta, caption.full_caption, caption.alt_text))

        conn.commit()
    finally:
        conn.close()


def determine_content_destination(media: MediaInfo, analysis, force_type: str = None) -> str:
    """
    Route content to appropriate upload flow.

    Args:
        media: MediaInfo object with metadata
        analysis: PhotoAnalysis or VideoAnalysis object
        force_type: Force a specific type ("reel", "story", "post", "carousel")

    Returns:
        Destination string: "feed_post", "reel", "story", or "carousel"
    """
    # Handle forced type
    if force_type:
        return force_type

    # Photos always go to feed posts (or stories if specified)
    if media.media_type == MediaType.PHOTO:
        return "feed_post"

    # Videos need routing logic
    if isinstance(analysis, VideoAnalysis):
        # Check if suitable for Reels
        if analysis.is_reel_suitable and media.aspect_ratio in ["vertical", "vertical_9_16", "square"]:
            return "reel"

        # Not suitable for Reels - check why
        if analysis.duration_warning:
            log(f"  Video routing note: {analysis.duration_warning}", level="INFO")

        # Fall back to feed video
        return "feed_post"

    return "feed_post"


def group_media_for_carousel(media_items: list[MediaInfo]) -> Optional[MediaGroup]:
    """
    Group media items for carousel posting.

    The user has already curated what belongs together by placing items
    in the album. This function validates the group is suitable for carousel.

    Args:
        media_items: List of MediaInfo objects from the album

    Returns:
        MediaGroup if suitable for carousel, None otherwise
    """
    # Need at least 2 items for carousel
    if len(media_items) < 2:
        return None

    # Filter to photos only (carousels typically don't mix well with videos)
    photos = [m for m in media_items if m.media_type == MediaType.PHOTO]
    if len(photos) < 2:
        return None  # Not enough photos

    # Check aspect ratios - allow up to 2 different ratios for variety
    aspect_ratios = set(p.aspect_ratio for p in photos)
    if len(aspect_ratios) > 2:
        return None  # Too varied aspect ratios

    # Limit to 10 items (Instagram carousel max)
    carousel_items = photos[:10]

    return MediaGroup(
        items=carousel_items,
        group_type="carousel",
        grouping_reason=f"{len(carousel_items)} photos from album"
    )


def generate_posting_pack(posts: list[dict], output_dir: Path) -> Path:
    """
    Generate a posting pack: a folder with numbered subfolders,
    each containing the media file, a caption.txt, and a schedule time.

    The user opens Meta Business Suite, drags in the media, pastes the caption,
    and sets the schedule time.

    Returns:
        Path to the posting pack directory
    """
    timestamp = datetime.now().strftime("%Y-%m-%d")
    pack_dir = output_dir / f"posting-pack-{timestamp}"
    pack_dir.mkdir(parents=True, exist_ok=True)

    for i, post in enumerate(posts, 1):
        slot_dir = pack_dir / f"{i:02d}-{post['schedule_time'].strftime('%a-%b-%d-%I%p')}"
        slot_dir.mkdir(parents=True, exist_ok=True)

        media_path = Path(post["media_path"])

        # Copy media file into the slot folder
        import shutil
        dest_media = slot_dir / media_path.name
        if not dest_media.exists():
            shutil.copy2(media_path, dest_media)

        # Write caption to a text file (easy to copy-paste)
        caption_file = slot_dir / "caption.txt"
        caption_file.write_text(post["caption"])

        # Write a README with instructions
        readme_file = slot_dir / "README.txt"
        media_type = post.get("media_type", "post")
        schedule_str = post["schedule_time"].strftime("%A %B %d at %I:%M %p")
        readme_file.write_text(
            f"Post {i} — {media_type.upper()}\n"
            f"{'=' * 40}\n\n"
            f"Schedule: {schedule_str}\n"
            f"Media:    {media_path.name}\n"
            f"Size:     {media_path.stat().st_size / 1024 / 1024:.1f} MB\n\n"
            f"How to post:\n"
            f"  1. Open Meta Business Suite → Content → Create\n"
            f"  2. Select 'Reel' (for videos) or 'Post' (for photos)\n"
            f"  3. Drag in: {media_path.name}\n"
            f"  4. Open caption.txt and paste into the caption field\n"
            f"  5. Click 'Schedule' and set date/time to: {schedule_str}\n"
            f"  6. Click Schedule to confirm\n"
        )

    return pack_dir


def generate_report(posts: list[dict], output_dir: Path) -> Path:
    """Generate a report of scheduled posts."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    report_path = output_dir / f"report_{timestamp}.md"

    lines = [
        "# Instagram Auto-Post Report",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## Scheduled Posts",
        "",
    ]

    for i, post in enumerate(posts, 1):
        media_type = post.get('media_type', 'photo')
        lines.append(f"### Post {i} ({media_type})")
        lines.append(f"- **Media:** {post.get('media_path', 'N/A')}")
        lines.append(f"- **Scheduled:** {post.get('schedule_time', 'N/A')}")
        lines.append(f"- **Status:** {post.get('status', 'pending')}")
        if post.get('analysis', {}).get('video_type'):
            lines.append(f"- **Video Type:** {post['analysis']['video_type']}")
        if post.get('analysis', {}).get('duration'):
            lines.append(f"- **Duration:** {post['analysis']['duration']:.1f}s")
        lines.append("")
        lines.append("**Caption:**")
        lines.append("```")
        lines.append(post.get('caption', 'N/A'))
        lines.append("```")
        lines.append("")

    report_content = "\n".join(lines)
    report_path.write_text(report_content)

    return report_path


def run_workflow(
    dry_run: bool = False,
    use_ai: bool = True,
    max_count: int = 3,
    force_type: str = None,
    enable_carousel: bool = False,
    from_output: bool = False,
) -> dict:
    """
    Run the complete auto-post workflow.

    Args:
        dry_run: If True, don't actually schedule posts
        use_ai: If True, use AI for photo analysis
        max_count: Maximum number of photos to process (1-3)
        force_type: Force content type ("reel", "story", "post", "carousel")
        enable_carousel: If True, enable carousel grouping for multiple photos

    Returns:
        Dict with workflow results
    """
    results = {
        "started_at": datetime.now().isoformat(),
        "status": "pending",
        "posts": [],
        "errors": [],
    }

    log("Starting auto-post workflow")

    try:
        if from_output:
            # --- Output directory mode: skip Photos app entirely ---
            log("Source: output/framed/ directory (bypassing Photos app)")
            media_items = collect_from_output_dir()
            log(f"Found {len(media_items)} framed media items")
        else:
            # --- Default: Photos app flow ---
            # Step 1: Ensure Photos app is running
            log("Ensuring Photos app is running...")
            if not ensure_photos_app_running():
                raise Exception("Could not start Photos app")
            log("Photos app ready")

            # Step 2: Create albums if needed
            log("Creating albums if needed...")
            album_results = create_albums()
            log(f"Albums status: {album_results}")

            # Step 3: Get media from "To Post" album (photos and videos)
            log("Getting media from 'To Post' album...")
            media_items = get_media_from_album("To Post")

        # Count by type for reporting
        photos = [m for m in media_items if m.media_type == MediaType.PHOTO]
        videos = [m for m in media_items if m.media_type == MediaType.VIDEO]
        source_label = "output/framed/" if from_output else "'To Post' album"
        log(f"Found {len(photos)} photos, {len(videos)} videos in {source_label}")

        # Flexible media count: accept 1-3 items
        min_items = 1
        max_items = 4

        if len(media_items) < min_items:
            msg = "No media in 'To Post' album"
            log(msg, level="WARNING")
            results["status"] = "skipped"
            results["message"] = msg
            return results

        # Determine how many items to process (respect CLI override)
        media_count = min(len(media_items), max_items, max_count)
        log(f"Will process {media_count} media item(s)")

        # Check for carousel grouping if enabled
        carousel_group = None
        if enable_carousel and len(photos) >= 2:
            log("Checking for carousel grouping...")
            carousel_group = group_media_for_carousel(media_items)
            if carousel_group:
                log(f"Found carousel group: {len(carousel_group.items)} items")
                log(f"  Grouping reason: {carousel_group.grouping_reason}")
                # Override media_count for carousel
                media_count = 1  # One carousel post
            else:
                log("No suitable carousel group found")

        # Step 4: Get posting schedule (only as many slots as media)
        schedule = get_posting_schedule(count=media_count)
        log(f"Posting schedule for {media_count} post(s): {[s.strftime('%A %I:%M %p') for s in schedule]}")

        # Step 5: Process media (photos and videos)
        temp_dir = get_temp_export_dir()
        if not from_output:
            clear_temp_exports()

        posts_to_schedule = []

        # Handle carousel group if found
        if carousel_group:
            log("Processing carousel group...")
            carousel_paths = []
            for idx, item in enumerate(carousel_group.items):
                log(f"  Exporting carousel item {idx+1}: {item.filename}")
                # Find index of this item in media_items
                item_index = next((i for i, m in enumerate(media_items) if m.id == item.id), -1)
                if item_index >= 0:
                    path = export_media_by_index("To Post", item_index, temp_dir)
                    if path:
                        carousel_paths.append(path)
                        log(f"    Exported to: {path}")
                    else:
                        log(f"    Failed to export item {idx+1}", level="ERROR")

            if len(carousel_paths) >= 2:
                # Analyze first photo for caption
                first_photo_path = carousel_paths[0]
                log("  Analyzing first photo for caption...")
                analysis = analyze_photo(first_photo_path, use_ai=use_ai)
                log(f"  Detected: {analysis.piece_type}, {analysis.content_type.value}")

                # Generate caption (carousels use standard caption format)
                caption = generate_caption(analysis)
                log(f"  Caption length: {len(caption.full_caption)} chars")

                # Save full PhotoAnalysis as dict for feedback learning
                analysis_dict = dataclasses.asdict(analysis)
                # Convert enum to string for JSON serialization
                analysis_dict["content_type"] = analysis.content_type.value

                posts_to_schedule.append({
                    "media_paths": carousel_paths,
                    "media_path": carousel_paths[0],  # For compatibility
                    "media_type": "carousel",
                    "original_type": "carousel",
                    "caption": caption.full_caption,
                    "alt_text": caption.alt_text,
                    "schedule_time": schedule[0],
                    "media_id": f"carousel_{len(carousel_paths)}",
                    "media_index": 0,
                    "card_count": len(carousel_paths),
                    "analysis": analysis_dict
                })
            else:
                log("  Not enough items for carousel, falling back to individual posts")
                carousel_group = None  # Reset to process individually

        # Process individual media (if not carousel or carousel failed)
        if not carousel_group:
            for i in range(media_count):
                media = media_items[i]
                is_video = media.media_type == MediaType.VIDEO
                media_type_str = "video" if is_video else "photo"
                log(f"Processing {media_type_str} {i+1}: {media.filename}")
                log(f"  Aspect ratio: {media.aspect_ratio}")

                # Export media (or use direct path if from_output)
                if from_output and hasattr(media, '_file_path'):
                    media_path = media._file_path
                    log(f"  Using existing file: {media_path}")
                else:
                    log(f"  Exporting {media_type_str}...")
                    media_path = export_media_by_index("To Post", i, temp_dir)

                if not media_path:
                    error_msg = f"Failed to export {media_type_str} {i+1}"
                    log(error_msg, level="ERROR")
                    results["errors"].append(error_msg)
                    continue

                log(f"  Exported to: {media_path}")

                # Analyze media (photo or video)
                log(f"  Analyzing {media_type_str}...")
                analysis_degraded = False
                try:
                    if is_video:
                        # Get video info for duration and dimensions
                        video_info = get_video_info(media_path)
                        duration = video_info.get("duration", media.duration if media.duration > 0 else 0)
                        width = video_info.get("width", media.width)
                        height = video_info.get("height", media.height)

                        analysis = analyze_video(
                            media_path,
                            use_ai=use_ai,
                            duration=duration,
                            width=width,
                            height=height
                        )
                        log(f"  Detected: {analysis.video_type} video, {analysis.duration_seconds}s")
                        if analysis.duration_warning:
                            log(f"  Warning: {analysis.duration_warning}", level="WARNING")
                        log(f"  Reel suitable: {analysis.is_reel_suitable}")
                    else:
                        analysis = analyze_photo(media_path, use_ai=use_ai)
                        log(f"  Detected: {analysis.piece_type}, {analysis.content_type.value}")
                except Exception as e:
                    log(f"  Analysis failed, using defaults: {e}", level="ERROR")
                    analysis_degraded = True
                    if is_video:
                        analysis = VideoAnalysis(
                            content_type=ContentType.PROCESS_VIDEO,
                            video_type="process",
                            duration_seconds=media.duration if media.duration > 0 else 30.0,
                            primary_colors=["earth tones"],
                            activity="pottery making",
                            mood="warm",
                            has_audio=False,
                            suggested_hook="Pottery process video",
                            is_reel_suitable=False,
                            aspect_ratio_category=media.aspect_ratio,
                            duration_warning=None
                        )
                    else:
                        analysis = PhotoAnalysis(
                            content_type=ContentType.FINISHED_PIECE,
                            piece_type="piece",
                            primary_colors=["earth tones"],
                            secondary_colors=[],
                            glaze_type=None,
                            technique=None,
                            mood="warm",
                            is_process=False,
                            dimensions_visible=False,
                            suggested_hook="Handmade ceramic piece"
                        )

                # Determine content destination
                destination = determine_content_destination(media, analysis, force_type)
                log(f"  Content destination: {destination}")

                # Generate caption
                log("  Generating caption...")
                is_reel = destination == "reel"
                caption = generate_caption(analysis, is_reel=is_reel)
                log(f"  Caption length: {len(caption.full_caption)} chars")

                # Persist caption to feedback.db for dashboard access
                try:
                    _save_caption_to_db(media.filename, caption)
                except Exception as e:
                    log(f"  Warning: Could not save caption to DB: {e}", level="WARNING")

                # Save full analysis as dict for feedback learning
                analysis_dict = dataclasses.asdict(analysis)
                # Convert enum to string for JSON serialization
                analysis_dict["content_type"] = analysis.content_type.value

                posts_to_schedule.append({
                    "media_path": media_path,
                    "media_type": destination,  # feed_post, reel, story
                    "original_type": media_type_str,
                    "caption": caption.full_caption,
                    "alt_text": caption.alt_text,
                    "schedule_time": schedule[i],
                    "media_id": media.id,
                    "media_index": i,
                    "analysis": analysis_dict,
                    "analysis_degraded": analysis_degraded,
                })

        if len(posts_to_schedule) < 1:
            error_msg = f"Only {len(posts_to_schedule)} posts ready, expected {media_count}"
            log(error_msg, level="ERROR")
            results["status"] = "partial"
            results["errors"].append(error_msg)

        # Step 5.5: Auto-generate frames for series photos (skip for from_output — already framed)
        if not from_output:
            for post in posts_to_schedule:
                if post.get("original_type") != "photo":
                    continue  # Skip videos/carousels
                media_path = post.get("media_path", "")
                filename = Path(media_path).name
                planet_data = get_planet_data_from_db(filename)
                if planet_data:
                    log(f"  Photo '{filename}' is in a series, generating frame...")
                    try:
                        framed_path = frame_single_photo(media_path, planet_data)
                        post["framed_path"] = framed_path
                        log(f"  Framed image saved: {framed_path}")
                    except Exception as e:
                        log(f"  Frame generation failed: {e}", level="WARNING")
                        post["frame_error"] = str(e)

        # Step 6: Generate posting pack (copy media + write captions + schedule times)
        log("Generating posting pack...")
        pack_dir = generate_posting_pack(posts_to_schedule, get_output_dir())
        log(f"Posting pack saved to: {pack_dir}")

        for post in posts_to_schedule:
            post["status"] = "ready"
            results["posts"].append(post)

        # Step 7: Move media to "Posted" album (skip for from_output mode)
        if from_output:
            log("Skipping 'move to Posted' (from-output mode)")
        else:
            log("Moving media to 'Posted' album...")
        for post in posts_to_schedule:
            if post.get("status") in ["scheduled", "dry_run"]:
                if from_output:
                    pass  # Skip move for from_output mode
                elif dry_run:
                    log(f"  Would move {post['original_type']} {post['media_index'] + 1} to 'Posted'")
                else:
                    success = move_photo_by_index("To Post", "Posted", post["media_index"])
                    if success:
                        log(f"  Moved {post['original_type']} {post['media_index'] + 1} to 'Posted'")
                    else:
                        log(f"  Failed to move {post['original_type']} {post['media_index'] + 1}", level="WARNING")

        # Step 8: Generate report
        log("Generating report...")
        report_path = generate_report(results["posts"], get_reports_dir())
        log(f"Report saved to: {report_path}")

        # Clean up temp files (only for Photos app exports)
        if not from_output:
            clear_temp_exports()

        # Set final status
        if len(results["errors"]) == 0:
            results["status"] = "success"
        else:
            results["status"] = "partial"

        log(f"Workflow completed with status: {results['status']}")

    except Exception as e:
        log(f"Workflow failed: {e}", level="ERROR")
        results["status"] = "failed"
        results["errors"].append(str(e))

    results["completed_at"] = datetime.now().isoformat()

    # Save results JSON
    results_path = get_reports_dir() / f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, default=str)

    return results


def show_status() -> None:
    """Show the current pipeline status."""
    print("=" * 60)
    print("Instagram Auto-Post Pipeline Status")
    print("=" * 60)

    # Check albums
    print("\n📷 Albums:")
    to_post_count = get_photo_count("To Post")
    posted_count = get_photo_count("Posted")

    print(f"   'To Post' album: {to_post_count} photos")
    print(f"   'Posted' album: {posted_count} photos")

    # Check next schedule
    print("\n📅 Next Schedule (based on available photos):")
    schedule_count = min(to_post_count, 3) if to_post_count > 0 else 3
    schedule = get_posting_schedule(count=schedule_count)
    for i, dt in enumerate(schedule, 1):
        print(f"   Post {i}: {dt.strftime('%A %B %d at %I:%M %p')}")

    # Check recent reports
    print("\n📊 Recent Reports:")
    reports_dir = get_reports_dir()
    reports = sorted(reports_dir.glob("report_*.md"), reverse=True)[:3]

    if reports:
        for report in reports:
            print(f"   {report.name}")
    else:
        print("   No reports yet")

    # Check logs
    print("\n📝 Recent Log Entries:")
    log_file = get_logs_dir() / "auto-post.log"
    if log_file.exists():
        with open(log_file) as f:
            lines = f.readlines()[-5:]
            for line in lines:
                print(f"   {line.strip()}")
    else:
        print("   No logs yet")

    print("\n" + "=" * 60)

    # Recommendation (flexible: 1-3 photos)
    if to_post_count >= 1:
        print(f"✅ Ready to post {min(to_post_count, 3)} photo(s)! Run: python auto-post.py")
        if to_post_count > 3:
            print("   Note: Only first 3 photos will be processed this week")
    else:
        print("⚠️  Add at least 1 photo to 'To Post' album")

    print("=" * 60)


def test_cron() -> bool:
    """Test if cron job is set up correctly."""
    import subprocess

    print("=" * 60)
    print("Cron Job Test")
    print("=" * 60)

    # Check if crontab has our entry
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            workspace_path = str(get_workspace_root())
            print("\n❌ No crontab configured")
            print("\nTo set up cron, run:")
            print("   crontab -e")
            print("\nThen add this line:")
            print(f"   0 6 * * 1 cd {workspace_path} && /usr/bin/python3 instagram/scripts/auto-post.py >> instagram/logs/cron.log 2>&1")
            return False

        crontab = result.stdout

        # Look for our job
        workspace_path = str(get_workspace_root())
        if "auto-post.py" in crontab:
            print("\n✅ Cron job found!")
            for line in crontab.split("\n"):
                if "auto-post" in line:
                    print(f"   {line}")
        else:
            print("\n⚠️  Cron job not found")
            print("\nTo add, run: crontab -e")
            print("Then add:")
            print(f"   0 6 * * 1 cd {workspace_path} && /usr/bin/python3 instagram/scripts/auto-post.py >> instagram/logs/cron.log 2>&1")

        # Check script is executable
        script_path = Path(__file__)
        print(f"\n📄 Script: {script_path}")
        print(f"   Exists: {'✅' if script_path.exists() else '❌'}")

        # Check logs directory
        logs_dir = get_logs_dir()
        print(f"\n📁 Logs directory: {logs_dir}")
        print(f"   Exists: {'✅' if logs_dir.exists() else '❌'}")

    except Exception as e:
        print(f"\n❌ Error checking cron: {e}")
        return False

    print("\n" + "=" * 60)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Instagram Auto-Post Script",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python auto-post.py           Run normal workflow
    python auto-post.py --test    Run in test mode (dry run)
    python auto-post.py --status  Show pipeline status
    python auto-post.py --cron-test  Verify cron setup
    python auto-post.py --no-ai   Run without AI analysis
    python auto-post.py --reel    Force content as Reel
    python auto-post.py --story   Force content as Story
    python auto-post.py --carousel  Enable carousel grouping
    python auto-post.py --from-output --reel  Post framed videos as Reels
        """
    )

    parser.add_argument(
        "--test", "-t",
        action="store_true",
        help="Run in test mode (dry run, no actual posting)"
    )

    parser.add_argument(
        "--status", "-s",
        action="store_true",
        help="Show pipeline status"
    )

    parser.add_argument(
        "--cron-test",
        action="store_true",
        help="Test cron job setup"
    )

    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Disable AI photo analysis (use basic analysis)"
    )

    parser.add_argument(
        "--count", "-c",
        type=int,
        default=3,
        choices=[1, 2, 3, 4],
        help="Number of photos to process (default: 3, max: 4)"
    )

    parser.add_argument(
        "--reel",
        action="store_true",
        help="Force content as Reel (vertical video <90s)"
    )

    parser.add_argument(
        "--story",
        action="store_true",
        help="Force content as Story (24h ephemeral)"
    )

    parser.add_argument(
        "--carousel",
        action="store_true",
        help="Enable carousel grouping for multiple photos"
    )

    parser.add_argument(
        "--post",
        action="store_true",
        help="Force content as feed post (no routing)"
    )

    parser.add_argument(
        "--from-output",
        action="store_true",
        help="Read media from output/framed/ instead of Photos app"
    )

    args = parser.parse_args()

    if args.status:
        show_status()

    elif args.cron_test:
        test_cron()

    else:
        dry_run = args.test
        use_ai = not args.no_ai
        max_count = args.count

        # Determine force type
        force_type = None
        if args.reel:
            force_type = "reel"
        elif args.story:
            force_type = "story"
        elif args.post:
            force_type = "feed_post"

        print("=" * 60)
        print("Instagram Auto-Post")
        print("=" * 60)
        print(f"Mode: {'TEST (dry run)' if dry_run else 'LIVE'}")
        print(f"Source: {'output/framed/' if args.from_output else 'Photos app'}")
        print(f"AI Analysis: {'Enabled' if use_ai else 'Disabled'}")
        print(f"Max Photos: {max_count}")
        if force_type:
            print(f"Force Type: {force_type}")
        if args.carousel:
            print("Carousel: Enabled")
        print("=" * 60)

        results = run_workflow(
            dry_run=dry_run,
            use_ai=use_ai,
            max_count=max_count,
            force_type=force_type,
            enable_carousel=args.carousel,
            from_output=args.from_output,
        )

        print("\n" + "=" * 60)
        print("Results")
        print("=" * 60)
        print(f"Status: {results['status']}")
        print(f"Posts processed: {len(results['posts'])}")

        # Show content types
        for post in results['posts']:
            dest = post.get('media_type', 'unknown')
            orig = post.get('original_type', 'unknown')
            print(f"  - {Path(post['media_path']).name}: {orig} -> {dest}")

        if results['errors']:
            print("\nErrors:")
            for error in results['errors']:
                print(f"  - {error}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
