#!/usr/bin/env python3
"""
CLI tool for generating framed videos of spinning pottery.

Takes a video of pottery rotating on a banding wheel and applies the
planetary exploration frame (space background, HUD overlay, rim light)
so it looks like a planet rotating.

Architecture: 3-phase pipeline to avoid rembg multiprocessing contention.
  Phase 1: extract_masks — sequential rembg with keyframe interpolation
  Phase 2: composite — lightweight PIL ops (bg, glow, rim, zoom panels)
  Phase 3: re-hud — apply HUD overlay to composited video

Usage:
    python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8"
    python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --no-loop-detect
    python scripts/frame_video.py --re-hud already_framed.mp4 --planet "Pyr-os-8"
    python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --slowdown 1
    python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --masks-only
    python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --composite --masks-dir ./masks
"""

import argparse
import gc
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
from PIL import Image

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from video_frame_generator import VideoFrameGenerator
from frame_image import get_planet_data_from_db, get_vision_analysis
from frame_generator import (
    colors_to_chemistry_string,
    surface_to_geology_string,
    hypotheses_to_chemistry_string,
    extract_chemistry_from_hypotheses,
)
import sqlite3

FRAMED_OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "framed" / "video"

DB_PATH = Path(__file__).parent.parent.parent / "tools" / "feedback.db"

# Loop detection: edge-based MSE above this threshold = poor loop, skip crossfade
# Edge-based comparison is invariant to lighting/shadow changes that cause
# raw pixel MSE to spike even at perfect loop points (e.g., 5000+ on real footage).
LOOP_MSE_THRESHOLD = 2500

# Shorter crossfade for good loops (0.3s instead of 0.5s)
LOOP_CROSSFADE_SECONDS = 0.3


def get_planet_data_by_name(planet_name: str) -> dict | None:
    """Get planet data by planet name (for when video filename doesn't match DB photo)."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT planet_name, orbital_data, surface_geology, formation_history, order_index
        FROM series_pieces
        WHERE planet_name LIKE ?
        LIMIT 1
    """, (f"%{planet_name}%",))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "planet_name": row["planet_name"],
            "sector": row["orbital_data"],
            "surface_geology": row["surface_geology"],
            "log_number": row["order_index"],
            "lore": row["formation_history"],
        }
    return None


def get_photo_filename_by_planet(planet_name: str) -> str | None:
    """Get the original photo filename from DB for a given planet name."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("""
        SELECT photo FROM series_pieces WHERE planet_name LIKE ? LIMIT 1
    """, (f"%{planet_name}%",))
    row = cursor.fetchone()
    conn.close()
    return row["photo"] if row else None


def find_framed_photo(photo_filename: str) -> Path | None:
    """Find the framed version of a photo in output/framed/ directories."""
    base_name = Path(photo_filename).stem
    framed_dir = Path(__file__).parent.parent.parent / "output" / "framed"
    if not framed_dir.exists():
        return None
    # Search all subdirectories for matching framed photo
    for subdir in framed_dir.iterdir():
        if not subdir.is_dir():
            continue
        for f in subdir.glob(f"{base_name}*"):
            if f.suffix.lower() in ('.jpg', '.jpeg', '.png'):
                return f
    return None


def extract_zoom_panels_from_frame(frame_path: str) -> list:
    """Extract zoom panel regions from a video frame with coaster-aware masking.
    
    Extracts 3 regions from the pottery piece at different vertical positions:
    - Top: Upper body/glaze area
    - Middle: Mid-body transition  
    - Bottom: Lower body/foot
    
    Applies coaster mask cleaning to ensure no banding wheel in zoom panels.
    Returns list of 150x150 RGBA images.
    """
    from rembg import remove, new_session
    
    frame = Image.open(frame_path).convert('RGB')
    frame_rgba = frame.convert('RGBA')
    
    # Use rembg to get the pottery mask
    try:
        session = new_session()
        no_bg = remove(frame, session=session, post_process_mask=True)
    except Exception:
        frame.close()
        return []
    
    # Get alpha mask
    alpha = np.array(no_bg.split()[3])
    bbox = no_bg.getbbox()
    if not bbox:
        no_bg.close()
        frame.close()
        return []
    
    # Calculate zoom regions within the pottery bbox
    x1, y1, x2, y2 = bbox
    piece_w = x2 - x1
    piece_h = y2 - y1
    
    target_size = 150
    panel_size = min(300, piece_w // 2, piece_h // 3)
    
    # Define 3 vertical regions - ABOVE where coaster typically is
    # Adjusted to stay well within the pottery piece body
    regions = [
        (0.15, 0.28),  # Top: upper glaze (well above coaster)
        (0.32, 0.45),  # Upper-middle: glaze transition
        (0.50, 0.63),  # Lower: body/foot (above coaster area)
    ]
    
    panels = []
    
    for vy_top, vy_bottom in regions:
        # Calculate crop center
        cx = (x1 + x2) // 2
        cy = int(y1 + piece_h * ((vy_top + vy_bottom) / 2))
        
        half_size = panel_size // 2
        crop_x1 = max(0, cx - half_size)
        crop_y1 = max(0, cy - half_size)
        crop_x2 = min(frame.width, crop_x1 + panel_size)
        crop_y2 = min(frame.height, crop_y1 + panel_size)
        
        if crop_x2 - crop_x1 < 100 or crop_y2 - crop_y1 < 100:
            continue
        
        # Extract crop and apply alpha mask
        crop = frame_rgba.crop((crop_x1, crop_y1, crop_x2, crop_y2))
        crop_alpha = Image.fromarray(alpha[crop_y1:crop_y2, crop_x1:crop_x2], mode='L')
        crop.putalpha(crop_alpha)
        
        # Check if crop has enough valid content (>30% non-transparent)
        alpha_arr = np.array(crop_alpha)
        valid_ratio = np.sum(alpha_arr > 128) / alpha_arr.size
        
        if valid_ratio < 0.3:
            # Not enough content, skip
            crop.close()
            continue
        
        if crop.size != (target_size, target_size):
            crop = crop.resize((target_size, target_size), Image.Resampling.LANCZOS)
        panels.append(crop)
    
    # Fill missing panels by duplicating valid ones
    while len(panels) < 3:
        if panels:
            panels.append(panels[0].copy())
        else:
            panels.append(Image.new('RGBA', (target_size, target_size), (50, 50, 50, 255)))
    
    no_bg.close()
    frame.close()
    return panels[:3]


def enrich_planet_data(planet_data: dict, photo_filename: str) -> dict:
    """Enrich planet_data with vision analysis (chemistry, firing, clay, anomalies, etc.).

    Same enrichment that frame_single_photo() does for static frames.
    """
    vision = get_vision_analysis(photo_filename)
    if not vision:
        return planet_data

    # Chemistry from hypotheses or colors
    if "chemistry" not in planet_data or not planet_data.get("chemistry"):
        chemistry = hypotheses_to_chemistry_string(vision.get("hypotheses"))
        if chemistry:
            planet_data["chemistry"] = chemistry
        else:
            chemistry = colors_to_chemistry_string(vision["primary_colors"])
            if chemistry:
                planet_data["chemistry"] = chemistry

    # Vision fields → worldbuilding fields (only if DB data is missing/generic)
    if vision.get("surface_qualities"):
        planet_data["surface_qualities"] = ", ".join(vision["surface_qualities"])
    if vision.get("technique"):
        clay = vision.get("clay_type", "stoneware")
        clay_label = clay.replace("_", " ").title() if clay else "stoneware"
        planet_data["origin"] = f"{vision['technique'].title()}, {clay_label} substrate"
    if vision.get("hypotheses"):
        anomalies = extract_chemistry_from_hypotheses(vision["hypotheses"])
        if anomalies:
            planet_data["anomalies"] = anomalies
    if vision.get("firing_state"):
        planet_data["firing_state"] = vision["firing_state"]
    if vision.get("clay_type"):
        planet_data["clay_type"] = vision["clay_type"]

    return planet_data


def find_loop_point(frame_dir: Path, start_frame: int, end_frame: int,
                    fps: int = 30, min_loop_seconds: float = 2.0) -> tuple[int, float]:
    """
    Detect loop point within a frame range using edge-based comparison.

    Uses FIND_EDGES filter on grayscale frames, which is invariant to
    uniform brightness changes, shadows, and lighting shifts that cause
    raw pixel MSE to spike even at perfect loop points.

    Args:
        frame_dir: Directory containing frame_000001.png, etc.
        start_frame: First frame (1-indexed).
        end_frame: Last frame (1-indexed, inclusive).
        fps: Video frame rate (for computing minimum loop length).
        min_loop_seconds: Minimum loop duration in seconds (default 2.0).

    Returns:
        Tuple of (best_frame_1indexed, best_mse).
    """
    from PIL import ImageFilter

    frames = sorted(frame_dir.glob("frame_*.png"))
    # Downscale for speed (360px wide is plenty for loop detection)
    sample = Image.open(frames[start_frame - 1])
    thumb_size = (360, int(360 * sample.height / sample.width))
    first = np.array(
        sample.convert('L').resize(thumb_size).filter(ImageFilter.FIND_EDGES),
        dtype=np.float64,
    )
    sample.close()

    # Require at least one full rotation worth of frames
    min_loop_frames = int(min_loop_seconds * fps)
    actual_skip = min(start_frame + min_loop_frames - 1, end_frame)

    best_idx = actual_skip
    best_mse = float('inf')

    for i in range(actual_skip, end_frame + 1):
        img = Image.open(frames[i - 1])
        frame = np.array(
            img.convert('L').resize(thumb_size).filter(ImageFilter.FIND_EDGES),
            dtype=np.float64,
        )
        img.close()
        mse = np.mean((first - frame) ** 2)
        if mse < best_mse:
            best_mse = mse
            best_idx = i

    return best_idx, best_mse


def extract_frames(video_path: str, frame_dir: Path, max_width: int = 1920) -> int:
    """Extract frames from video using ffmpeg. Returns count of frames."""
    frame_dir.mkdir(parents=True, exist_ok=True)

    # Build video filter chain
    # Note: ffmpeg auto-rotates based on container metadata, so explicit
    # transpose filters are not needed (and would double-rotate).
    vf_parts = []
    # Scale down to max_width if needed — 4K frames are overkill for analysis
    if max_width:
        vf_parts.append(f"scale=min({max_width}\\,iw):-2")
    vf = ','.join(vf_parts) if vf_parts else None

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vsync', '0',
    ]
    if vf:
        cmd += ['-vf', vf]
    cmd.append(str(frame_dir / 'frame_%06d.png'))
    subprocess.run(cmd, capture_output=True, check=True)
    return len(list(frame_dir.glob('frame_*.png')))


def assemble_video(frame_dir: Path, output_path: Path, num_frames: int,
                   fps: int = 30, fade_seconds: float = 0.3,
                   intermediate_ext: str = 'jpg',
                   slowdown: int = 1) -> None:
    """Assemble processed frames into MP4 with optional crossfade loop using ffmpeg.

    Args:
        slowdown: Frame duration multiplier. 2 = each frame shown twice (half speed).
                  Input framerate becomes fps/slowdown but output stays at fps.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame_pattern = f'frame_%06d.{intermediate_ext}'
    input_fps = max(1, fps // slowdown)  # Read frames slower → slower playback
    effective_duration = num_frames / input_fps  # Actual video duration

    if fade_seconds > 0 and num_frames > 10:
        # Two-pass: build raw video, then crossfade end into beginning
        raw_path = output_path.with_suffix('.raw.mp4')
        cmd_raw = [
            'ffmpeg', '-y',
            '-framerate', str(input_fps),
            '-start_number', '1',
            '-i', str(frame_dir / frame_pattern),
            '-c:v', 'libx264',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),  # Encode at full fps for smooth output
            str(raw_path),
        ]
        subprocess.run(cmd_raw, capture_output=True, check=True)

        offset = effective_duration - fade_seconds
        cmd_xfade = [
            'ffmpeg', '-y',
            '-i', str(raw_path),
            '-i', str(raw_path),
            '-filter_complex', f'[1]trim=duration={fade_seconds}[begin];[0][begin]xfade=transition=fade:duration={fade_seconds}:offset={offset}[out]',
            '-map', '[out]',
            '-c:v', 'libx264',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            str(output_path),
        ]
        subprocess.run(cmd_xfade, capture_output=True, check=True)
        raw_path.unlink(missing_ok=True)
    else:
        cmd = [
            'ffmpeg', '-y',
            '-framerate', str(input_fps),
            '-start_number', '1',
            '-i', str(frame_dir / frame_pattern),
            '-c:v', 'libx264',
            '-crf', '18',
            '-pix_fmt', 'yuv420p',
            '-r', str(fps),  # Encode at full fps for smooth output
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)


def get_video_fps(video_path: str) -> int:
    """Get video FPS using ffprobe."""
    cmd = [
        'ffprobe', '-v', 'error',
        '-select_streams', 'v:0',
        '-show_entries', 'stream=r_frame_rate',
        '-of', 'csv=p=0',
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    rate_str = result.stdout.strip().split(',')[0].split('\n')[0].strip()
    if '/' in rate_str:
        num, den = rate_str.split('/')
        return int(round(int(num) / int(den)))
    return int(round(float(rate_str)))


# =========================================================================
# Progress bar helper
# =========================================================================

def _progress_bar(completed: int, total: int, t0: float, bar_width: int = 30) -> None:
    """Write a progress bar to stdout."""
    pct = completed / total
    filled = int(bar_width * pct)
    bar = '\u2588' * filled + '\u2591' * (bar_width - filled)
    elapsed = time.time() - t0
    if elapsed > 0 and completed > 0:
        fps_proc = completed / elapsed
        eta = (total - completed) / fps_proc
        eta_str = f"{int(eta // 60)}m{int(eta % 60):02d}s" if eta >= 60 else f"{eta:.0f}s"
    else:
        fps_proc = 0
        eta_str = "..."
    sys.stdout.write(f'\r  [{bar}] {completed}/{total} ({pct:.0%}) {fps_proc:.1f}f/s ETA {eta_str}')
    sys.stdout.flush()


# =========================================================================
# Phase 1: Extract masks with keyframe interpolation
# =========================================================================

def extract_masks_with_interpolation(generator: VideoFrameGenerator,
                                     frame_dir: Path, masks_dir: Path,
                                     loop_point: int, mask_interval: int = 3) -> None:
    """
    Phase 1: Extract alpha masks using rembg on every Nth frame, interpolate the rest.

    Runs sequentially with a single rembg model — no multiprocessing,
    no thread contention. Keyframe interpolation provides the speedup.

    Args:
        generator: VideoFrameGenerator with rembg session loaded
        frame_dir: Directory of raw frames (frame_000001.png, etc.)
        masks_dir: Output directory for mask PNGs
        loop_point: Number of frames to process
        mask_interval: Run rembg every Nth frame (default 3)
    """
    masks_dir.mkdir(parents=True, exist_ok=True)

    # Determine keyframe indices (0-indexed)
    keyframe_indices = list(range(0, loop_point, mask_interval))
    # Ensure last frame is a keyframe for complete coverage
    if keyframe_indices[-1] != loop_point - 1:
        keyframe_indices.append(loop_point - 1)

    # Phase 1a: Extract masks on keyframes
    keyframe_masks = {}
    t0 = time.time()
    total_keyframes = len(keyframe_indices)

    print(f"  Phase 1a: Extracting masks on {total_keyframes} keyframes (every {mask_interval}th)...")
    for ki, idx in enumerate(keyframe_indices):
        frame_path = frame_dir / f"frame_{idx + 1:06d}.png"
        if not frame_path.exists():
            continue

        frame = Image.open(frame_path)
        try:
            mask = generator.extract_mask(frame)
            keyframe_masks[idx] = mask
            mask.save(masks_dir / f"mask_{idx + 1:06d}.png")
        finally:
            frame.close()

        if ki % 5 == 0:
            gc.collect()

        n = ki + 1
        _progress_bar(n, total_keyframes, t0)

    sys.stdout.write('\n')
    elapsed = time.time() - t0
    print(f"  Phase 1a: {total_keyframes} keyframe masks in {elapsed:.1f}s "
          f"({total_keyframes / elapsed:.1f}f/s)")

    # Phase 1b: Interpolate between keyframes
    t0 = time.time()
    interp_count = loop_point - total_keyframes
    print(f"  Phase 1b: Interpolating {interp_count} intermediate masks...")

    for idx in range(loop_point):
        if idx in keyframe_masks:
            continue

        # Find surrounding keyframes
        prev_kf = max(k for k in keyframe_masks if k <= idx)
        next_kf = min(k for k in keyframe_masks if k >= idx)

        if prev_kf == next_kf:
            # No interpolation needed (edge case)
            mask = keyframe_masks[prev_kf]
        else:
            # Linear interpolation: mask_n = prev * (1-t) + next * t
            t = (idx - prev_kf) / (next_kf - prev_kf)
            prev_arr = np.array(keyframe_masks[prev_kf], dtype=np.float32)
            next_arr = np.array(keyframe_masks[next_kf], dtype=np.float32)
            interp_arr = (prev_arr * (1 - t) + next_arr * t).astype(np.uint8)
            mask = Image.fromarray(interp_arr, mode='L')

        mask.save(masks_dir / f"mask_{idx + 1:06d}.png")

    elapsed = time.time() - t0
    print(f"  Phase 1b: {interp_count} interpolated masks in {elapsed:.1f}s")


# =========================================================================
# Phase 2: Composite frames (lightweight PIL ops)
# =========================================================================

def composite_frames(generator: VideoFrameGenerator,
                     frame_dir: Path, masks_dir: Path, composited_dir: Path,
                     loop_point: int, start_frame: int = 0) -> None:
    """
    Phase 2: Composite raw frames onto space background using pre-extracted masks.

    Pure PIL operations — no ML models, no thread contention.
    Safe to parallelize later if needed.

    Args:
        generator: VideoFrameGenerator with cached state from frame 0
        frame_dir: Directory of raw frames
        masks_dir: Directory of pre-extracted alpha masks
        composited_dir: Output directory for composited JPGs
        loop_point: Number of frames to process
        start_frame: First frame to process (default 0, set to 1 to skip bootstrap)
    """
    composited_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    frame_count = loop_point - start_frame

    print(f"  Phase 2: Compositing {frame_count} frames (starting at {start_frame})...")
    for i in range(start_frame, loop_point):
        frame_path = frame_dir / f"frame_{i + 1:06d}.png"
        mask_path = masks_dir / f"mask_{i + 1:06d}.png"
        if not frame_path.exists() or not mask_path.exists():
            continue

        frame = Image.open(frame_path)
        mask = Image.open(mask_path)
        composited = None
        try:
            composited = generator.composite_frame(frame, mask,
                                                   frame_index=i,
                                                   total_frames=loop_point)
            composited.save(composited_dir / f"frame_{i + 1:06d}.jpg", quality=95)
        finally:
            frame.close()
            mask.close()
            if composited is not None:
                composited.close()

        if i % 10 == 0:
            gc.collect()

        _progress_bar(i - start_frame + 1, frame_count, t0)

    sys.stdout.write('\n')
    elapsed = time.time() - t0
    print(f"  Phase 2: {frame_count} frames in {elapsed:.1f}s ({frame_count / elapsed:.1f}f/s)")


# =========================================================================
# Phase 3: Re-HUD (apply HUD overlay to composited video)
# =========================================================================

def apply_rehud(generator: VideoFrameGenerator,
                input_video: Path, output_path: Path,
                total_frames: int, output_fps: int,
                slowdown: int = 1) -> None:
    """
    Phase 3: Extract frames from composited video and apply HUD overlay.

    Args:
        generator: VideoFrameGenerator (animate flag controls animated vs static)
        input_video: Path to composited video (no HUD)
        output_path: Path for final output video (with HUD)
        total_frames: Number of frames
        output_fps: Output FPS
        slowdown: Frame duration multiplier
    """
    with tempfile.TemporaryDirectory(prefix="rehud_") as tmpdir:
        tmpdir = Path(tmpdir)
        rehud_frames = tmpdir / "rehud_frames"
        rehud_frames.mkdir()

        # Extract frames from no-HUD video
        extract_frames(str(input_video), rehud_frames)

        processed_frames = tmpdir / "processed"
        processed_frames.mkdir()
        t0 = time.time()

        print(f"  Phase 3: Applying HUD to {total_frames} frames...")
        for i in range(total_frames):
            frame_path = rehud_frames / f"frame_{i + 1:06d}.png"
            if not frame_path.exists():
                continue

            frame = Image.open(frame_path)
            processed = None
            try:
                processed = generator.apply_hud_only(frame, frame_index=i,
                                                     total_frames=total_frames)
                processed.save(processed_frames / f"frame_{i + 1:06d}.jpg", quality=95)
            finally:
                frame.close()
                if processed is not None:
                    processed.close()

            if i % 10 == 0:
                gc.collect()

            _progress_bar(i + 1, total_frames, t0)

        sys.stdout.write('\n')
        elapsed = time.time() - t0
        print(f"  Phase 3: {total_frames} frames in {elapsed:.1f}s ({total_frames / elapsed:.1f}f/s)")

        # Assemble final video
        print("  Assembling final video...", end=" ", flush=True)
        assemble_video(processed_frames, output_path, total_frames, output_fps, fade_seconds=0,
                       slowdown=slowdown)
        print("done")


# =========================================================================
# Main
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generate framed video of spinning pottery (3-phase pipeline)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full pipeline: extract masks → composite → HUD
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8"

  # Phase 1 only: extract masks (for caching / debugging)
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --masks-only

  # Phase 2 only: composite using existing masks
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --composite --masks-dir ./masks

  # Phase 3 only: re-apply HUD
  python scripts/frame_video.py --re-hud already_framed.mp4 --planet "Pyr-os-8"

  # Skip loop detection, no crossfade
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --no-loop-detect

  # Full speed (override default slowdown 2)
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --slowdown 1

  # Custom mask interval (rembg every 5th frame instead of 3rd)
  python scripts/frame_video.py --input spinning.mp4 --planet "Pyr-os-8" --mask-interval 5
"""
    )

    parser.add_argument("--input", default=None, help="Path to input video (MP4, MOV)")
    parser.add_argument("--re-hud", default=None, metavar="INPUT_VIDEO",
                        help="Re-apply HUD to an already-framed video (skip rembg/glow/rim)")
    parser.add_argument("--planet", required=True, help="Planet name")
    parser.add_argument("--zoom", type=float, default=1.0,
                        help="Piece fill ratio (default: 1.0 = fills art area). Try 1.1-1.2 for planet close-up")
    parser.add_argument("--slowdown", type=int, default=1,
                        help="Frame duration multiplier (default: 1 = normal). 2 = half speed. Source is 60fps iPhone, output at 30fps = natural slow-mo")
    parser.add_argument("--loop-point", type=int, default=None,
                        help="Manually specify loop frame")
    parser.add_argument("--output", default=None,
                        help="Output filename (without extension). Default: {planet_name}_rotating")
    parser.add_argument("--no-loop-detect", action="store_true", default=True,
                        help="Skip loop detection, use entire video (default: True)")
    parser.add_argument("--loop-detect", action="store_true",
                        help="Enable loop detection (crossfade at loop point)")
    parser.add_argument("--no-animate", action="store_true",
                        help="Disable animated HUD effects (static overlay)")
    parser.add_argument("--no-sound", action="store_true",
                        help="Disable UI sound design")
    parser.add_argument("--audio-only", action="store_true",
                        help="Only regenerate and mix audio into existing video (no frame processing)")
    parser.add_argument("--zoom-photo", default=None, metavar="PATH",
                        help="Path to framed photo (2x) to extract zoom panels from (re-HUD mode only)")
    parser.add_argument("--boot-duration", type=float, default=0.5,
                        help="HUD boot-up sequence duration in seconds (default: 0.5)")

    # Phase control flags
    parser.add_argument("--masks-only", action="store_true",
                        help="Phase 1 only: extract masks and stop (no composite, no HUD)")
    parser.add_argument("--composite", action="store_true",
                        help="Phase 2 only: composite using existing masks from --masks-dir")
    parser.add_argument("--masks-dir", default=None, metavar="PATH",
                        help="Directory of pre-extracted masks (for --composite)")
    parser.add_argument("--mask-interval", type=int, default=3,
                        help="Run rembg every Nth frame, interpolate the rest (default: 3)")

    args = parser.parse_args()

    re_hud_mode = args.re_hud is not None
    masks_only_mode = args.masks_only
    composite_only_mode = args.composite
    audio_only_mode = args.audio_only

    if audio_only_mode:
        if not args.input:
            parser.error("--audio-only requires --input")
    elif re_hud_mode:
        pass  # re-hud mode is valid on its own
    elif composite_only_mode:
        if not args.input:
            parser.error("--composite requires --input")
        if not args.masks_dir:
            parser.error("--composite requires --masks-dir")
    elif not args.input:
        parser.error("Either --input, --re-hud, or --composite is required")

    input_path = Path(args.re_hud if re_hud_mode else args.input)
    if not input_path.exists():
        print(f"Error: Video not found: {input_path}")
        sys.exit(1)

    if composite_only_mode and args.masks_dir:
        masks_dir = Path(args.masks_dir)
        if not masks_dir.exists():
            print(f"Error: Masks directory not found: {masks_dir}")
            sys.exit(1)

    if not shutil.which('ffmpeg'):
        print("Error: ffmpeg not found. Install with: brew install ffmpeg")
        sys.exit(1)

    # Get planet data from DB (try by filename first, then by planet name)
    planet_data = get_planet_data_from_db(input_path.stem)
    if planet_data is None:
        planet_data = get_planet_data_by_name(args.planet)
    if planet_data is None:
        planet_data = {
            "planet_name": args.planet,
            "sector": "Unknown Sector",
            "surface_geology": "Uncharted terrain",
            "log_number": hash(args.planet) % 999 + 1,
        }
        print(f"  No planet data in DB, using defaults for '{args.planet}'")
    else:
        print(f"  Planet: {planet_data['planet_name']}")

    # Get video info
    mode_label = "RE-HUD" if re_hud_mode else ("COMPOSITE" if composite_only_mode else
               ("MASKS-ONLY" if masks_only_mode else "INPUT"))
    print(f"{mode_label}: {input_path}")
    fps = get_video_fps(str(input_path))
    print(f"FPS: {fps}")

    animate = not args.no_animate
    do_sound = not args.no_sound
    output_fps = fps  # Always 30fps; slowdown controls frame duplication
    output_name = args.output or f"{planet_data['planet_name'].replace(' ', '_')}_rotating"
    output_path = FRAMED_OUTPUT_DIR / f"{output_name}.mp4"

    # =====================================================================
    # AUDIO-ONLY MODE: regenerate sound design on existing video
    # =====================================================================
    if audio_only_mode:
        # Get frame count without extracting frames
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0',
             '-show_entries', 'stream=nb_frames', '-of', 'csv=p=0',
             str(input_path)],
            capture_output=True, text=True
        )
        total_frames = int(probe.stdout.strip()) if probe.stdout.strip() else 469
        loop_point = total_frames
        output_path = input_path  # mix audio in-place
        print(f"AUDIO-ONLY: {total_frames} frames, {total_frames / fps:.1f}s at {fps}fps")

        # Enrich planet_data with vision analysis (needed for text elements)
        photo_filename = get_photo_filename_by_planet(args.planet)
        if photo_filename:
            planet_data = enrich_planet_data(planet_data, photo_filename)
            extra_keys = [k for k in ['chemistry', 'surface_qualities', 'origin',
                        'anomalies', 'firing_state', 'clay_type'] if k in planet_data]
            if extra_keys:
                print(f"  Vision enrichment: {', '.join(extra_keys)}")

    # =====================================================================
    # RE-HUD MODE: apply HUD to already-framed video (unchanged)
    # =====================================================================
    if re_hud_mode:
        with tempfile.TemporaryDirectory(prefix="frame_video_") as tmpdir:
            tmpdir = Path(tmpdir)
            all_frames = tmpdir / "all_raw"
            processed_frames = tmpdir / "processed"

            print("Extracting frames...", end=" ", flush=True)
            total_frames = extract_frames(str(input_path), all_frames)
            total_duration = total_frames / fps
            print(f" {total_frames} frames ({total_duration:.1f}s at {fps}fps)")

            loop_point = total_frames
            print(f"Re-HUD: applying {'animated' if animate else 'static'} HUD to all {total_frames} frames")

            # Load zoom panels from framed photo
            zoom_panels = None
            zoom_photo_path = Path(args.zoom_photo) if args.zoom_photo else None
            if zoom_photo_path and zoom_photo_path.exists():
                print(f"  Zoom panels: extracting from {zoom_photo_path.name}")
                zoom_panels = VideoFrameGenerator.extract_zoom_panels_from_photo(str(zoom_photo_path))
                print(f"  Zoom panels: {len(zoom_panels)} panels extracted")
            elif not args.zoom_photo:
                # Auto-lookup: find photo from DB and framed output
                photo_filename = get_photo_filename_by_planet(args.planet)
                if photo_filename:
                    framed_photo = find_framed_photo(photo_filename)
                    if framed_photo:
                        print(f"  Zoom panels: extracting from {framed_photo.name}")
                        zoom_panels = VideoFrameGenerator.extract_zoom_panels_from_photo(str(framed_photo))
                        print(f"  Zoom panels: {len(zoom_panels)} panels extracted")

            # Enrich planet_data with vision analysis (chemistry, firing, clay, etc.)
            photo_filename = get_photo_filename_by_planet(args.planet)
            if photo_filename:
                planet_data = enrich_planet_data(planet_data, photo_filename)
                extra_keys = [k for k in ['chemistry', 'surface_qualities', 'origin',
                            'anomalies', 'firing_state', 'clay_type'] if k in planet_data]
                if extra_keys:
                    print(f"  Vision enrichment: {', '.join(extra_keys)}")

            generator = VideoFrameGenerator(planet_data, animate=animate,
                                            photo_zoom_panels=zoom_panels)

            processed_frames.mkdir()
            t0 = time.time()
            for i in range(loop_point):
                frame_path = all_frames / f"frame_{i + 1:06d}.png"
                if not frame_path.exists():
                    continue

                frame = Image.open(frame_path)
                processed = None
                try:
                    processed = generator.apply_hud_only(frame, frame_index=i, total_frames=loop_point,
                                                          re_hud=True)
                    processed.save(processed_frames / f"frame_{i + 1:06d}.jpg", quality=95)
                finally:
                    frame.close()
                    if processed is not None:
                        processed.close()

                if i % 10 == 0:
                    gc.collect()

                _progress_bar(i + 1, loop_point, t0)

            sys.stdout.write('\n')
            elapsed_total = time.time() - t0
            print(f"  {loop_point} frames in {elapsed_total:.1f}s ({loop_point / elapsed_total:.1f}f/s)")

            print("Assembling video...", end=" ", flush=True)
            assemble_video(processed_frames, output_path, loop_point, fps, fade_seconds=0,
                           slowdown=args.slowdown)
            print("done")

    # =====================================================================
    # COMPOSITE-ONLY MODE: use existing masks, skip Phase 1
    # =====================================================================
    elif composite_only_mode:
        with tempfile.TemporaryDirectory(prefix="frame_video_") as tmpdir:
            tmpdir = Path(tmpdir)
            all_frames = tmpdir / "all_raw"
            composited_frames = tmpdir / "composited"

            print("Extracting frames...", end=" ", flush=True)
            total_frames = extract_frames(str(input_path), all_frames)
            total_duration = total_frames / fps
            print(f" {total_frames} frames ({total_duration:.1f}s at {fps}fps)")

            loop_point = total_frames

            # Bootstrap: process frame 0 to get ref crop, glow, rim, zoom
            t0 = time.time()
            print("  Bootstrapping frame 0 (ref crop, glow, rim, zoom regions)...", end=" ", flush=True)
            generator = VideoFrameGenerator(planet_data, zoom=args.zoom, animate=animate)

            frame_0_path = all_frames / "frame_000001.png"
            frame_0 = Image.open(frame_0_path)
            mask_0_path = masks_dir / "mask_000001.png"
            if not mask_0_path.exists():
                print(f"\n  Error: mask_000001.png not found in {masks_dir}")
                sys.exit(1)
            mask_0 = Image.open(mask_0_path)
            try:
                composited_0 = generator.composite_frame(frame_0, mask_0,
                                                         frame_index=0,
                                                         total_frames=loop_point)
                composited_0.save(composited_frames / "frame_000001.jpg", quality=95)
            finally:
                frame_0.close()
                mask_0.close()
                composited_0.close()
            print(f"done ({time.time() - t0:.1f}s)")

            # Composite all frames
            composite_frames(generator, all_frames, masks_dir, composited_frames, loop_point)

            # Assemble no-HUD video
            print("Assembling video (no HUD)...", end=" ", flush=True)
            assemble_video(composited_frames, output_path, loop_point, output_fps, fade_seconds=0,
                           slowdown=args.slowdown)
            print("done")

    # =====================================================================
    # NORMAL MODE (or MASKS-ONLY): 3-phase pipeline
    # =====================================================================
    elif not audio_only_mode:
        with tempfile.TemporaryDirectory(prefix="frame_video_") as tmpdir:
            tmpdir = Path(tmpdir)
            all_frames = tmpdir / "all_raw"
            masks_out = tmpdir / "masks"
            composited_frames = tmpdir / "composited"

            # Step 1: Extract all frames from video (1080px wide = Instagram Reel resolution)
            print("Extracting frames...", end=" ", flush=True)
            total_frames = extract_frames(str(input_path), all_frames, max_width=1080)
            total_duration = total_frames / fps
            print(f" {total_frames} frames ({total_duration:.1f}s at {fps}fps)")

            # Step 2: Detect loop point
            # Default (--no-loop-detect is True): use all frames, no crossfade
            # --loop-detect: run loop detection, maybe crossfade
            # --loop-point N: manual loop frame
            use_crossfade = False
            if args.loop_point is not None:
                loop_point = min(args.loop_point, total_frames)
                use_crossfade = True
                print(f"Using manual loop point: frame {loop_point}")
            elif args.loop_detect:
                print("Detecting loop point...", end=" ", flush=True)
                loop_idx, loop_mse = find_loop_point(all_frames, 1, total_frames)
                if loop_mse < LOOP_MSE_THRESHOLD:
                    loop_point = loop_idx
                    use_crossfade = True
                    print(f"frame {loop_point} (MSE: {loop_mse:.1f} — good loop, crossfade ON)")
                else:
                    loop_point = total_frames
                    print(f"MSE: {loop_mse:.1f} — poor loop ({LOOP_MSE_THRESHOLD} threshold), using all {total_frames} frames")
            else:
                loop_point = total_frames
                print(f"Using all {total_frames} frames (loop detection off by default)")

            anim_label = "animated" if animate else "static"
            print(f"Processing {loop_point} frames (zoom {args.zoom}x, output {output_fps}fps, {anim_label}, mask interval {args.mask_interval})")

            # =================================================================
            # Phase 1: Extract masks with keyframe interpolation
            # =================================================================
            t_total = time.time()
            t_phase1 = time.time()

            # Enrich planet_data with vision analysis (needed for HUD text elements)
            photo_filename = get_photo_filename_by_planet(args.planet)
            if photo_filename:
                planet_data = enrich_planet_data(planet_data, photo_filename)
                extra_keys = [k for k in ['chemistry', 'surface_qualities', 'origin',
                            'anomalies', 'firing_state', 'clay_type'] if k in planet_data]
                if extra_keys:
                    print(f"  Vision enrichment: {', '.join(extra_keys)}")

            # Extract zoom panels from frame 0 (for video processing)
            zoom_panels = None
            frame_0_path = all_frames / "frame_000001.png"
            if frame_0_path.exists():
                print("  Extracting zoom panels from frame 0...", end=" ", flush=True)
                zoom_panels = extract_zoom_panels_from_frame(str(frame_0_path))
                if zoom_panels:
                    print(f"{len(zoom_panels)} panels")
                else:
                    print("skipped")
            
            generator = VideoFrameGenerator(planet_data, zoom=args.zoom, animate=animate,
                                            photo_zoom_panels=zoom_panels)

            # Pre-compute coaster mask using temporal variance (before phase 1)
            print("  Pre-computing coaster mask (temporal variance)...", end=" ", flush=True)
            debug_dir = output_path.parent / "debug" / output_path.stem
            generator.precompute_coaster_mask(all_frames, total_frames, debug_dir=debug_dir)
            t_precomp = time.time() - t_phase1
            print(f"done ({t_precomp:.1f}s)")

            extract_masks_with_interpolation(
                generator, all_frames, masks_out, loop_point,
                mask_interval=args.mask_interval,
            )

            t_phase1_elapsed = time.time() - t_phase1
            print(f"  Phase 1 total: {t_phase1_elapsed:.1f}s")

            # If masks-only, copy masks out and stop
            if masks_only_mode:
                dest_masks = Path(args.masks_dir) if args.masks_dir else (Path.cwd() / "masks")
                if not dest_masks.exists():
                    dest_masks.mkdir(parents=True)
                    print(f"  Created masks directory: {dest_masks}")
                print(f"  Copying masks to {dest_masks}...", end=" ", flush=True)
                for mask_file in sorted(masks_out.glob("mask_*.png")):
                    shutil.copy2(mask_file, dest_masks / mask_file.name)
                print(f"done ({len(list(masks_out.glob('mask_*.png')))} masks)")
                print("\nDone: masks extracted. Use --composite --masks-dir to composite.")
                return

            # =================================================================
            # Phase 2: Bootstrap frame 0 + composite all frames
            # =================================================================
            t_phase2 = time.time()

            # Bootstrap: process frame 0 to get ref crop, glow, rim, zoom
            print("  Bootstrapping frame 0 (ref crop, glow, rim, zoom regions)...", end=" ", flush=True)
            composited_frames.mkdir()

            frame_0_path = all_frames / "frame_000001.png"
            mask_0_path = masks_out / "mask_000001.png"
            frame_0 = Image.open(frame_0_path)
            mask_0 = Image.open(mask_0_path)
            composited_0 = None
            try:
                composited_0 = generator.composite_frame(frame_0, mask_0,
                                                         frame_index=0,
                                                         total_frames=loop_point)
                composited_0.save(composited_frames / "frame_000001.jpg", quality=95)
            finally:
                frame_0.close()
                mask_0.close()
                if composited_0 is not None:
                    composited_0.close()
            print(f"done ({time.time() - t_phase2:.1f}s)")

            # Composite remaining frames (1..N-1, skip frame 0 — already bootstrapped)
            composite_frames(generator, all_frames, masks_out, composited_frames,
                             loop_point, start_frame=1)

            t_phase2_elapsed = time.time() - t_phase2
            print(f"  Phase 2 total: {t_phase2_elapsed:.1f}s")

            # =================================================================
            # Assemble no-HUD video
            # =================================================================
            no_hud_path = tmpdir / "no_hud.mp4"
            print("Assembling video (no HUD)...", end=" ", flush=True)
            fade = LOOP_CROSSFADE_SECONDS if use_crossfade else 0
            assemble_video(composited_frames, no_hud_path, loop_point, output_fps,
                           fade_seconds=fade, intermediate_ext='jpg',
                           slowdown=args.slowdown)
            print("done")

            # =================================================================
            # Phase 3: Apply HUD
            # =================================================================
            t_phase3 = time.time()

            rehud_generator = VideoFrameGenerator(planet_data, animate=animate)
            apply_rehud(rehud_generator, no_hud_path, output_path, loop_point, output_fps,
                        slowdown=args.slowdown)

            t_phase3_elapsed = time.time() - t_phase3
            print(f"  Phase 3 total: {t_phase3_elapsed:.1f}s")

            t_total_elapsed = time.time() - t_total
            print(f"\n  Pipeline total: {t_total_elapsed:.1f}s")
            print(f"    Phase 1 (masks):     {t_phase1_elapsed:.1f}s")
            print(f"    Phase 2 (composite): {t_phase2_elapsed:.1f}s")
            print(f"    Phase 3 (HUD):       {t_phase3_elapsed:.1f}s")

    # =====================================================================
    # Sound design (all modes except masks-only)
    # =====================================================================
    if not masks_only_mode and do_sound:
        try:
            from sound_design import generate_all_sounds, mix_sounds_with_video

            video_duration = loop_point / (fps if audio_only_mode else output_fps)

            with tempfile.TemporaryDirectory(prefix="frame_video_sounds_") as sound_tmpdir:
                sound_tmpdir = Path(sound_tmpdir)
                sound_dir = sound_tmpdir / "sounds"

                # Compute typewriter timing from boot sequence
                if animate:
                    # Use the same timing engine as the HUD animation
                    generator_for_timing = VideoFrameGenerator(planet_data, animate=True)
                    # In re-HUD mode, match the no-boot-fade timing used by the visual HUD
                    if re_hud_mode:
                        generator_for_timing._no_boot_fade = True
                    bt = generator_for_timing._get_boot_timing(loop_point)
                    text_start_frame = bt['text_start']

                    # Use actual playback fps (source fps for re-HUD/audio-only, output_fps for normal)
                    actual_fps = fps if (re_hud_mode or audio_only_mode) else output_fps
                    text_start_sec = text_start_frame / actual_fps

                    te = generator_for_timing._text_elements
                    lore_chars = len(te.get('lore', ''))

                    # Label chars and value chars counted separately (visual types them in phases)
                    label_chars = min(sum(len(label) for label, value, col in te.get('stats', [])), 100)
                    value_chars = min(sum(len(value) for label, value, col in te.get('stats', [])), 200)

                    # Replicate the visual timing phases (video_frame_generator.py:386-390)
                    tw_speed = generator_for_timing._compute_typewriter_speed(loop_point)
                    lore_duration = lore_chars / tw_speed / actual_fps
                    pause_after_lore = 8 / actual_fps
                    label_duration = label_chars / tw_speed / actual_fps
                    pause_before_values = 15 / actual_fps
                    value_duration = value_chars / tw_speed / actual_fps

                    click_interval = 1.0 / (tw_speed * actual_fps)
                    click_times = []

                    # Phase 1: lore typing
                    t = text_start_sec
                    for _ in range(lore_chars):
                        click_times.append(t)
                        t += click_interval

                    # Phase 2: pause (no clicks)
                    t += pause_after_lore

                    # Phase 3: label typing
                    for _ in range(label_chars):
                        click_times.append(t)
                        t += click_interval

                    # Phase 4: pause (no clicks)
                    t += pause_before_values

                    # Phase 5: value typing
                    for _ in range(value_chars):
                        click_times.append(t)
                        t += click_interval

                    total_type_duration = (t - text_start_sec)
                    stat_completion_time = t + 0.3
                else:
                    boot_frames = int(args.boot_duration * output_fps)
                    text_start_sec = boot_frames / output_fps
                    click_times = []
                    t = text_start_sec
                    while t < text_start_sec + 2.0:
                        click_times.append(t)
                        t += 0.05
                    stat_completion_time = text_start_sec + 2.0 + 0.3

                # Compute actual visual boot duration (matches what viewer sees)
                if animate:
                    visual_boot_sec = text_start_frame / actual_fps
                else:
                    visual_boot_sec = args.boot_duration

                # Compute actual border start delay from visual timing
                border_delay_ms = int(bt['borders_start'] / actual_fps * 1000) if animate else 100

                # Compute when the last typing click should sound
                typing_end_time = max(click_times) + 0.02 if click_times else 0.0

                print("Generating UI sounds...", end=" ", flush=True)
                sounds = generate_all_sounds(
                    sound_dir, fps=output_fps,
                    boot_duration=visual_boot_sec,
                    border_delay_ms=border_delay_ms,
                    typewriter_timing=click_times,
                    stat_completion_time=stat_completion_time,
                )
                sounds['_typing_end_time'] = typing_end_time
                print("done")

                print("Mixing audio...", end=" ", flush=True)
                final_path = output_path.with_suffix('.with_audio.mp4')
                mix_sounds_with_video(output_path, sounds, final_path, video_duration)
                final_path.replace(output_path)
                print("done")
        except ImportError:
            print("  Sound design skipped (sound_design module not found)")
        except Exception as e:
            print(f"  Sound design skipped: {e}")

    duration = loop_point / output_fps * args.slowdown

    print(f"\nDone: {output_path}")
    print(f"  {duration:.1f}s, {loop_point} frames at {output_fps}fps ({args.slowdown}x slowdown)")


if __name__ == "__main__":
    main()
