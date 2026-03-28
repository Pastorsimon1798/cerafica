"""
Photo and video export module for macOS Photos app integration.

Uses AppleScript to interact with the Photos app for:
- Creating albums ("To Post", "Posted")
- Listing media (photos and videos) in albums
- Exporting media to file system
- Moving media between albums
"""

import subprocess
import json
import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
from enum import Enum
from fractions import Fraction


class MediaType(Enum):
    """Type of media item."""
    PHOTO = "photo"
    VIDEO = "video"      # Feed video (horizontal or long)
    REEL = "reel"        # Vertical, <90s
    STORY = "story"      # 24h ephemeral content


@dataclass
class MediaInfo:
    """Media metadata from Photos app."""
    id: str
    filename: str
    date: str
    width: int
    height: int
    album: str
    media_type: MediaType = MediaType.PHOTO
    duration: float = 0.0  # Duration in seconds (for videos)
    aspect_ratio: str = "horizontal"  # vertical_9_16, vertical, square, horizontal


@dataclass
class MediaGroup:
    """A group of media items for a carousel."""
    items: list["MediaInfo"]
    group_type: str  # "carousel", "single", "reel"
    grouping_reason: str  # Why these were grouped


def get_aspect_ratio_category(width: int, height: int) -> str:
    """Categorize video aspect ratio."""
    if height > width:
        ratio = height / width
        if 1.7 <= ratio <= 1.9:  # 9:16 is ~1.778
            return "vertical_9_16"
        return "vertical"
    elif abs(height - width) / max(height, width, 1) < 0.1:
        return "square"
    return "horizontal"


# Backward compatibility alias
PhotoInfo = MediaInfo


def run_applescript(script: str) -> tuple[bool, str]:
    """
    Run an AppleScript and return (success, output).

    Args:
        script: AppleScript code to execute

    Returns:
        Tuple of (success: bool, output: str)
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=60
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        else:
            return False, result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "AppleScript timed out"
    except Exception as e:
        return False, str(e)


def ensure_photos_app_running() -> bool:
    """Ensure Photos app is running, launch if needed."""
    script = '''
    tell application "Photos"
        activate
        delay 2
        return "ready"
    end tell
    '''
    success, output = run_applescript(script)
    return success and "ready" in output


def create_albums(albums: list[str] = None) -> dict[str, bool]:
    """
    Create albums if they don't exist.

    Args:
        albums: List of album names to create. Defaults to ["To Post", "Posted"]

    Returns:
        Dict mapping album name to success status
    """
    if albums is None:
        albums = ["To Post", "Posted"]

    results = {}

    for album_name in albums:
        # Check if album exists, create if not
        script = f'''
        tell application "Photos"
            set albumName to "{album_name}"
            set albumExists to false

            repeat with a in albums
                if name of a is albumName then
                    set albumExists to true
                    exit repeat
                end if
            end repeat

            if not albumExists then
                make new album named albumName
                return "created"
            else
                return "exists"
            end if
        end tell
        '''
        success, output = run_applescript(script)
        results[album_name] = success

    return results


def create_carousel_album() -> bool:
    """Create 'To Post - Carousel' album if needed."""
    results = create_albums(["To Post - Carousel"])
    return results.get("To Post - Carousel", False)


def get_media_from_album(album_name: str) -> list[MediaInfo]:
    """
    Get list of media (photos and videos) from an album.

    Args:
        album_name: Name of the album to get media from

    Returns:
        List of MediaInfo objects with media metadata
    """
    # Use <<<ITEM>>> as item delimiter to avoid conflict with date strings containing commas
    script = f'''
    tell application "Photos"
        set targetAlbum to missing value

        repeat with a in albums
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat

        if targetAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        set mediaList to {{}}
        repeat with p in media items of targetAlbum
            set mediaId to id of p
            set mediaFilename to filename of p
            set mediaDate to date of p as string
            set mediaWidth to width of p
            set mediaHeight to height of p

            set end of mediaList to mediaId & "|||" & mediaFilename & "|||" & mediaDate & "|||" & mediaWidth & "|||" & mediaHeight
        end repeat

        -- Join with unique delimiter that won't appear in dates
        set AppleScript's text item delimiters to "<<<ITEM>>>"
        set output to mediaList as string
        set AppleScript's text item delimiters to ""
        return output
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error getting media: {output}")
        return []

    if output == "ALBUM_NOT_FOUND":
        print(f"Album '{album_name}' not found")
        return []

    media_items = []
    if output:
        # Split on unique item delimiter
        for line in output.split("<<<ITEM>>>"):
            if "|||" in line:
                parts = line.split("|||")
                if len(parts) >= 5:
                    # Detect video by file extension
                    filename = parts[1].strip().lower()
                    is_video = any(ext in filename for ext in [".mov", ".mp4", ".m4v"])

                    # Parse dimensions
                    width = int(parts[3].strip()) if parts[3].strip().isdigit() else 0
                    height = int(parts[4].strip()) if parts[4].strip().isdigit() else 0

                    media_items.append(MediaInfo(
                        id=parts[0].strip(),
                        filename=parts[1].strip(),
                        date=parts[2].strip(),
                        width=width,
                        height=height,
                        album=album_name,
                        media_type=MediaType.VIDEO if is_video else MediaType.PHOTO,
                        duration=0.0,  # Will be detected during export if needed
                        aspect_ratio=get_aspect_ratio_category(width, height)
                    ))

    return media_items


def get_photos_from_album(album_name: str) -> list[PhotoInfo]:
    """
    Get list of photos from an album (backward compatible).

    Args:
        album_name: Name of the album to get photos from

    Returns:
        List of PhotoInfo/MediaInfo objects with photo metadata
    """
    return get_media_from_album(album_name)


def export_photo(photo_id: str, output_dir: str, filename: Optional[str] = None) -> Optional[str]:
    """
    Export a single photo to the output directory.

    Args:
        photo_id: The Photos app ID of the photo
        output_dir: Directory to export to
        filename: Optional custom filename (will use original if not provided)

    Returns:
        Path to exported file, or None if export failed
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    script = f'''
    tell application "Photos"
        set targetPhoto to missing value

        repeat with p in media items
            if id of p is "{photo_id}" then
                set targetPhoto to p
                exit repeat
            end if
        end repeat

        if targetPhoto is missing value then
            return "PHOTO_NOT_FOUND"
        end if

        -- Export the photo
        set exportPath to POSIX path of "{output_dir}"
        export {{targetPhoto}} to exportPath with using originals

        return "EXPORTED"
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error exporting photo: {output}")
        return None

    if output == "PHOTO_NOT_FOUND":
        print(f"Photo with ID {photo_id} not found")
        return None

    # Find the exported file (Photos app uses original filename)
    # Wait a moment for file system to catch up
    import time
    time.sleep(1)

    exported_files = list(Path(output_dir).glob("*"))
    if exported_files:
        # Return the most recently modified file
        latest = max(exported_files, key=lambda f: f.stat().st_mtime)
        return str(latest)

    return None


def export_media_by_id(album_name: str, media_id: str, output_dir: str) -> Optional[str]:
    """
    Export media by its ID within a specific album (faster than export_photo).

    Args:
        album_name: Name of the album containing the media
        media_id: The Photos app ID of the media item
        output_dir: Directory to export to

    Returns:
        Path to exported file, or None if export failed
    """
    os.makedirs(output_dir, exist_ok=True)

    script = f'''
    tell application "Photos"
        set targetAlbum to missing value

        repeat with a in albums
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat

        if targetAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        set targetMedia to missing value
        repeat with m in media items of targetAlbum
            if id of m is "{media_id}" then
                set targetMedia to m
                exit repeat
            end if
        end repeat

        if targetMedia is missing value then
            return "MEDIA_NOT_FOUND"
        end if

        set mediaFilename to filename of targetMedia
        set exportPath to POSIX file "{output_dir}/"

        export {{targetMedia}} to exportPath as alias with using originals

        return mediaFilename
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error exporting media: {output}")
        return None

    if output in ["ALBUM_NOT_FOUND", "MEDIA_NOT_FOUND"]:
        print(f"Export failed: {output}")
        return None

    # The file should be in output_dir with the original filename
    exported_path = Path(output_dir) / output
    if exported_path.exists():
        return str(exported_path)

    # Fallback: find most recently modified file
    exported_files = list(Path(output_dir).glob("*"))
    if exported_files:
        latest = max(exported_files, key=lambda f: f.stat().st_mtime)
        return str(latest)

    return None


def export_photo_by_index(album_name: str, index: int, output_dir: str) -> Optional[str]:
    """
    Export a photo by its index in an album.

    This is more reliable than using photo IDs for export.

    Args:
        album_name: Name of the album
        index: Zero-based index of photo in album
        output_dir: Directory to export to

    Returns:
        Path to exported file, or None if export failed
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    script = f'''
    tell application "Photos"
        set targetAlbum to missing value

        repeat with a in albums
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat

        if targetAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        set albumPhotos to media items of targetAlbum
        set photoCount to count of albumPhotos

        if photoCount is 0 then
            return "NO_PHOTOS"
        end if

        if {index} >= photoCount then
            return "INDEX_OUT_OF_RANGE"
        end if

        set targetPhoto to item ({index} + 1) of albumPhotos
        set photoFilename to filename of targetPhoto
        set exportPath to POSIX file "{output_dir}/"

        export {{targetPhoto}} to exportPath as alias with using originals

        return photoFilename
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error exporting photo: {output}")
        return None

    if output in ["ALBUM_NOT_FOUND", "NO_PHOTOS", "INDEX_OUT_OF_RANGE"]:
        print(f"Export failed: {output}")
        return None

    # The file should be in output_dir with the original filename
    exported_path = Path(output_dir) / output
    if exported_path.exists():
        return str(exported_path)

    # Try to find any recent file
    import time
    time.sleep(1)
    exported_files = list(Path(output_dir).glob("*"))
    if exported_files:
        latest = max(exported_files, key=lambda f: f.stat().st_mtime)
        return str(latest)

    return None


def move_to_album(photo_id: str, from_album: str, to_album: str) -> bool:
    """
    Move a photo from one album to another.

    Note: This adds the photo to the destination album but doesn't remove
    it from the source album (Photos app limitation via AppleScript).

    Args:
        photo_id: The Photos app ID of the photo
        from_album: Source album name (for logging)
        to_album: Destination album name

    Returns:
        True if successful, False otherwise
    """
    script = f'''
    tell application "Photos"
        set targetPhoto to missing value
        set destAlbum to missing value

        -- Find the photo
        repeat with p in media items
            if id of p is "{photo_id}" then
                set targetPhoto to p
                exit repeat
            end if
        end repeat

        if targetPhoto is missing value then
            return "PHOTO_NOT_FOUND"
        end if

        -- Find the destination album
        repeat with a in albums
            if name of a is "{to_album}" then
                set destAlbum to a
                exit repeat
            end if
        end repeat

        if destAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        -- Add photo to destination album
        add {{targetPhoto}} to destAlbum

        return "MOVED"
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error moving photo: {output}")
        return False

    return output == "MOVED"


def move_photo_by_index(from_album: str, to_album: str, index: int) -> bool:
    """
    Move a photo by its index from one album to another.

    Args:
        from_album: Source album name
        to_album: Destination album name
        index: Zero-based index of photo in source album

    Returns:
        True if successful, False otherwise
    """
    script = f'''
    tell application "Photos"
        set sourceAlbum to missing value
        set destAlbum to missing value

        -- Find source album
        repeat with a in albums
            if name of a is "{from_album}" then
                set sourceAlbum to a
                exit repeat
            end if
        end repeat

        -- Find destination album
        repeat with a in albums
            if name of a is "{to_album}" then
                set destAlbum to a
                exit repeat
            end if
        end repeat

        if sourceAlbum is missing value or destAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        set albumPhotos to media items of sourceAlbum
        set photoCount to count of albumPhotos

        if photoCount is 0 then
            return "NO_PHOTOS"
        end if

        if {index} >= photoCount then
            return "INDEX_OUT_OF_RANGE"
        end if

        set targetPhoto to item ({index} + 1) of albumPhotos
        add {{targetPhoto}} to destAlbum

        return "MOVED"
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error moving photo: {output}")
        return False

    return output == "MOVED"


def get_photo_count(album_name: str) -> int:
    """Get the number of photos in an album."""
    script = f'''
    tell application "Photos"
        set targetAlbum to missing value

        repeat with a in albums
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat

        if targetAlbum is missing value then
            return "-1"
        end if

        return (count of media items of targetAlbum) as string
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        return -1

    try:
        return int(output)
    except ValueError:
        return -1


def get_temp_export_dir() -> str:
    """Get a temporary directory for photo exports."""
    temp_dir = Path(tempfile.gettempdir()) / "ceramics_instagram_exports"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return str(temp_dir)


def import_photo_to_album(file_path: str, album_name: str) -> bool:
    """Import a photo file into the macOS Photos app and add to album."""
    script = f'''
    tell application "Photos"
        set posixPath to POSIX file "{file_path}"
        try
            set importedPhoto to import posixPath
            tell application "Photos"
                set albumExists to false
                repeat with a in albums
                    if name of a is "{album_name}" then
                        set albumExists to true
                        exit repeat
                    end if
                end repeat
                if not albumExists then
                    make new album named "{album_name}"
                end if
                add importedPhoto to album "{album_name}"
            end tell
            return "OK"
        on error errMsg
            return "ERROR: " & errMsg
        end try
    end tell
    '''
    success, output = run_applescript(script)
    return success and "OK" in output


def clear_temp_exports() -> None:
    """Clear the temporary export directory."""
    temp_dir = get_temp_export_dir()
    if Path(temp_dir).exists():
        shutil.rmtree(temp_dir)
        Path(temp_dir).mkdir(parents=True, exist_ok=True)


def is_video_file(filepath: str) -> bool:
    """Check if a file is a video based on extension."""
    video_extensions = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".wmv"}
    return Path(filepath).suffix.lower() in video_extensions


def get_video_info(video_path: str) -> dict:
    """
    Get video metadata using ffprobe (if available) or macOS mdls as fallback.

    Returns dict with duration, width, height, fps, or empty dict if unavailable.
    """
    import shutil
    import platform

    info = {}

    # Try ffprobe first (most complete)
    if shutil.which("ffprobe"):
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    video_path
                ],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                data = json.loads(result.stdout)
                video_stream = next(
                    (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                    None
                )

                if video_stream:
                    width = video_stream.get("width", 0)
                    height = video_stream.get("height", 0)

                    # Check for rotation metadata (iPhone videos store landscape + rotation flag)
                    for side_data in video_stream.get("side_data_list", []):
                        rotation = side_data.get("rotation", 0)
                        if abs(rotation) == 90:
                            # Swap dimensions for 90° rotation
                            width, height = height, width
                            break

                    info = {
                        "width": width,
                        "height": height,
                        "duration": float(data.get("format", {}).get("duration", 0)),
                        "fps": float(Fraction(video_stream.get("r_frame_rate", "0/1"))),
                    }
                    return info
        except Exception:
            pass

    # Fallback: macOS mdls (native, always available)
    if platform.system() == "Darwin" and Path(video_path).exists():
        try:
            result = subprocess.run(
                ["mdls", "-name", "kMDItemDurationSeconds",
                 "-name", "kMDItemPixelWidth",
                 "-name", "kMDItemPixelHeight",
                 video_path],
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode == 0:
                import re
                # Parse mdls output: kMDItemDurationSeconds = 12.5
                for line in result.stdout.split("\n"):
                    if "kMDItemDurationSeconds" in line:
                        match = re.search(r'=\s*([\d.]+)', line)
                        if match:
                            info["duration"] = float(match.group(1))
                    elif "kMDItemPixelWidth" in line:
                        match = re.search(r'=\s*(\d+)', line)
                        if match:
                            info["width"] = int(match.group(1))
                    elif "kMDItemPixelHeight" in line:
                        match = re.search(r'=\s*(\d+)', line)
                        if match:
                            info["height"] = int(match.group(1))
        except Exception:
            pass

    return info


def export_media_by_index(album_name: str, index: int, output_dir: str) -> Optional[str]:
    """
    Export media (photo or video) by its index in an album.

    This is more reliable than using media IDs for export.
    Works for both photos and videos.

    Args:
        album_name: Name of the album
        index: Zero-based index of media in album
        output_dir: Directory to export to (must exist)

    Returns:
        Path to exported file, or None if export failed
    """
    # Ensure output directory exists
    os.makedirs(output_dir, exist_ok=True)

    script = f'''
    tell application "Photos"
        set targetAlbum to missing value

        repeat with a in albums
            if name of a is "{album_name}" then
                set targetAlbum to a
                exit repeat
            end if
        end repeat

        if targetAlbum is missing value then
            return "ALBUM_NOT_FOUND"
        end if

        set albumMedia to media items of targetAlbum
        set mediaCount to count of albumMedia

        if mediaCount is 0 then
            return "NO_MEDIA"
        end if

        if {index} >= mediaCount then
            return "INDEX_OUT_OF_RANGE"
        end if

        set targetMedia to item ({index} + 1) of albumMedia
        set mediaFilename to filename of targetMedia
        set exportPath to POSIX file "{output_dir}/"

        export {{targetMedia}} to exportPath as alias with using originals

        return mediaFilename
    end tell
    '''

    success, output = run_applescript(script)

    if not success:
        print(f"Error exporting media: {output}")
        return None

    if output in ["ALBUM_NOT_FOUND", "NO_MEDIA", "INDEX_OUT_OF_RANGE"]:
        print(f"Export failed: {output}")
        return None

    # The file should be in output_dir with the original filename
    exported_path = Path(output_dir) / output
    if exported_path.exists():
        return str(exported_path)

    # Try to find any recent file (might have different name)
    import time
    time.sleep(1)
    exported_files = list(Path(output_dir).glob("*"))
    if exported_files:
        latest = max(exported_files, key=lambda f: f.stat().st_mtime)
        return str(latest)

    return None


def test_module():
    """Test the photo/video export module."""
    print("=" * 60)
    print("Photo/Video Export Module Test")
    print("=" * 60)

    # 1. Ensure Photos app is running
    print("\n1. Ensuring Photos app is running...")
    if ensure_photos_app_running():
        print("   ✓ Photos app is ready")
    else:
        print("   ✗ Failed to launch Photos app")
        return

    # 2. Create albums
    print("\n2. Creating albums...")
    results = create_albums()
    for album, success in results.items():
        status = "✓" if success else "✗"
        print(f"   {status} {album}")

    # 3. Get media count
    print("\n3. Checking 'To Post' album...")
    count = get_photo_count("To Post")
    if count >= 0:
        print(f"   ✓ Found {count} media items in 'To Post' album")
    else:
        print("   ✗ Could not get media count")
        return

    if count == 0:
        print("\n   Note: Add some photos/videos to 'To Post' album to test export")
        print("   Skipping export test")
        return

    # 4. List media (photos and videos)
    print("\n4. Listing media in 'To Post' album...")
    media_items = get_media_from_album("To Post")
    if media_items:
        photos = [m for m in media_items if m.media_type == MediaType.PHOTO]
        videos = [m for m in media_items if m.media_type == MediaType.VIDEO]

        print(f"   ✓ Found {len(photos)} photos, {len(videos)} videos:")
        for i, item in enumerate(media_items[:5]):  # Show first 5
            type_icon = "📹" if item.media_type == MediaType.VIDEO else "📷"
            duration_str = f" ({item.duration:.1f}s)" if item.duration > 0 else ""
            print(f"      {i+1}. {type_icon} {item.filename} ({item.width}x{item.height}){duration_str}")
        if len(media_items) > 5:
            print(f"      ... and {len(media_items) - 5} more")
    else:
        print("   ✗ No media found or error occurred")

    # 5. Test export (if media available)
    if media_items:
        print("\n5. Testing media export...")
        temp_dir = get_temp_export_dir()
        print(f"   Export directory: {temp_dir}")

        exported = export_media_by_index("To Post", 0, temp_dir)
        if exported:
            print(f"   ✓ Exported to: {exported}")
            file_size = Path(exported).stat().st_size
            is_video = is_video_file(exported)
            type_str = "video" if is_video else "photo"
            print(f"   File type: {type_str}")
            print(f"   File size: {file_size / 1024:.1f} KB")

            # Get video info if it's a video
            if is_video:
                video_info = get_video_info(exported)
                if video_info:
                    print(f"   Video info: {video_info.get('width')}x{video_info.get('height')}, "
                          f"{video_info.get('duration', 0):.1f}s")
        else:
            print("   ✗ Export failed")

        # Clean up
        clear_temp_exports()

    print("\n" + "=" * 60)
    print("Test complete!")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_module()
    else:
        print("Usage: python photo_export.py --test")
        print("       Tests the photo export module")
