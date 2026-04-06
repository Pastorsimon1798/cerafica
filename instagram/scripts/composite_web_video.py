#!/usr/bin/env python3
"""
Lightweight video compositing for Cerafica website.

Removes background from pottery spinning videos and composites onto
a procedurally generated space background. No HUD, no glow, no rim light,
no frame — just the pottery floating in space.

Usage:
    python composite_web_video.py --input ~/Downloads/IMG_4949.mov --planet "Pyr-os-8"
    python composite_web_video.py --input ~/Downloads/IMG_4950.mov --planet "Ignix-5"
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance
from rembg import new_session, remove

sys.path.insert(0, str(Path(__file__).parent))
from lib.frame_generator import SpaceBackground

# Web output settings
OUTPUT_WIDTH = 720
OUTPUT_HEIGHT = 1280  # 9:16 portrait ratio
CRF = 28  # H.264 quality (18=high, 28=medium, 35=low)
FPS = 24  # Cap at 24fps for web
PIECE_FILL = 0.80  # Piece fills 80% of output height


def process_video(input_path: str, planet_name: str, output_dir: str = None) -> Path | None:
    """Process a raw spinning video: bg removal + space composite.

    Args:
        input_path: Path to raw .mov/.mp4 file
        planet_name: Product name (used for output filename)
        output_dir: Output directory (defaults to output/web_video/)

    Returns:
        Path to output MP4, or None on failure.
    """
    input_path = Path(input_path)
    if not input_path.exists():
        print(f"Error: {input_path} not found")
        return None

    if output_dir is None:
        output_dir = Path(__file__).parent / "output" / "web_video"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    slug = planet_name.lower().replace(" ", "-").replace("_", "-")
    output_path = output_dir / f"{slug}_rotating.mp4"

    # --- Probe input video ---
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,r_frame_rate,duration",
         "-of", "csv=p=0", str(input_path)],
        capture_output=True, text=True
    )
    if probe.returncode != 0 or not probe.stdout.strip():
        print(f"Error: ffprobe failed for {input_path}")
        return None

    parts = probe.stdout.strip().split(",")
    input_w, input_h = int(parts[0]), int(parts[1])

    fps_parts = parts[2].split("/")
    input_fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else float(fps_parts[0])
    output_fps = min(input_fps, FPS)

    duration = float(parts[3]) if len(parts) > 3 and parts[3] else 10.0
    est_frames = int(duration * output_fps)

    print(f"Input:  {input_w}x{input_h} @ {input_fps:.1f}fps, {duration:.1f}s")
    print(f"Output: {OUTPUT_WIDTH}x{OUTPUT_HEIGHT} @ {output_fps}fps → {output_path}")

    # --- Init rembg (u2net is fast and accurate enough for pottery on dark bg) ---
    print("Loading rembg model (u2net)...")
    session = new_session(model_name="u2net")

    # --- Generate space background (once) ---
    print("Generating space background...")
    space_bg = SpaceBackground(OUTPUT_WIDTH, OUTPUT_HEIGHT, seed=42).generate().convert("RGBA")

    # --- Detect piece bounding box from first frame ---
    print("Detecting pottery region from first frame...")
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    extract_cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-i", str(input_path),
        "-frames:v", "1",
        tmp_path
    ]
    result = subprocess.run(extract_cmd, capture_output=True)
    if result.returncode != 0:
        print(f"Error: could not extract first frame: {result.stderr.decode()[:200]}")
        return None

    first_frame = Image.open(tmp_path).convert("RGB")
    first_enhanced = ImageEnhance.Contrast(first_frame).enhance(1.1)
    first_enhanced = ImageEnhance.Color(first_enhanced).enhance(1.15)
    no_bg = remove(first_enhanced, session=session, post_process_mask=True, alpha_matting=True)

    bbox = no_bg.getbbox()
    if bbox:
        pad_x = int((bbox[2] - bbox[0]) * 0.15)
        pad_y = int((bbox[3] - bbox[1]) * 0.15)
        crop = (
            max(0, bbox[0] - pad_x),
            max(0, bbox[1] - pad_y),
            min(input_w, bbox[2] + pad_x),
            min(input_h, bbox[3] + pad_y),
        )
    else:
        crop = (0, 0, input_w, input_h)

    crop_w = crop[2] - crop[0]
    crop_h = crop[3] - crop[1]

    # --- Calculate target dimensions ---
    max_h = int(OUTPUT_HEIGHT * PIECE_FILL)
    max_w = int(OUTPUT_WIDTH * 0.90)

    crop_ratio = crop_w / crop_h
    max_ratio = max_w / max_h

    if crop_ratio > max_ratio:
        target_w = max_w
        target_h = int(max_w / crop_ratio)
    else:
        target_h = max_h
        target_w = int(max_h * crop_ratio)

    x = (OUTPUT_WIDTH - target_w) // 2
    y = (OUTPUT_HEIGHT - target_h) // 2

    print(f"Piece crop: {crop_w}x{crop_h} → scaled to {target_w}x{target_h} at ({x}, {y})")

    # Cleanup temp file
    Path(tmp_path).unlink(missing_ok=True)

    # --- Process all frames via temp directory (avoids pipe deadlock) ---
    print(f"Processing ~{est_frames} frames...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        frames_dir = tmp_dir / "frames"
        out_frames_dir = tmp_dir / "out"
        frames_dir.mkdir()
        out_frames_dir.mkdir()

        # Step 1: Decode input video to PNG frames
        print("  Extracting frames...")
        decode_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(input_path),
            "-vf", f"fps={output_fps}",
            "-start_number", "0",
            str(frames_dir / "frame_%05d.png")
        ]
        result = subprocess.run(decode_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Decode error: {result.stderr[:300]}")
            return None

        frame_files = sorted(frames_dir.glob("frame_*.png"))
        actual_frames = len(frame_files)
        print(f"  Extracted {actual_frames} frames")

        # Step 2: Process each frame
        for i, frame_path in enumerate(frame_files):
            frame = Image.open(frame_path).convert("RGB")
            frame = ImageEnhance.Contrast(frame).enhance(1.1)
            frame = ImageEnhance.Color(frame).enhance(1.15)

            # Crop to piece region
            cropped = frame.crop(crop)

            # Downscale for faster rembg (target is 720p, 1.5x is plenty)
            rembg_scale = min(1.5, max(target_w, target_h) / max(crop_w, crop_h))
            if rembg_scale < 1.0:
                rembg_w = max(100, int(crop_w * rembg_scale))
                rembg_h = max(100, int(crop_h * rembg_scale))
                cropped_small = cropped.resize((rembg_w, rembg_h), Image.Resampling.LANCZOS)
            else:
                cropped_small = cropped
                rembg_scale = 1.0

            # Remove background on scaled crop
            no_bg_small = remove(cropped_small, session=session, post_process_mask=True, alpha_matting=True)

            # Kill bottom 8% of mask (banding wheel)
            arr = np.array(no_bg_small)
            h = arr.shape[0]
            arr[int(h * 0.92):, :, 3] = 0

            # Extract alpha mask and upscale to original crop size
            mask_small = Image.fromarray(arr[:, :, 3], mode="L")
            if rembg_scale < 1.0:
                mask = mask_small.resize((crop_w, crop_h), Image.Resampling.LANCZOS)
            else:
                mask = mask_small

            # Apply mask to full-res crop
            no_bg = cropped.copy().convert("RGBA")
            no_bg.putalpha(mask)

            # Scale piece to target size
            piece_scaled = no_bg.resize((target_w, target_h), Image.Resampling.LANCZOS)

            # Composite onto space background
            canvas = space_bg.copy()
            canvas.paste(piece_scaled, (x, y), piece_scaled)

            canvas.convert("RGB").save(out_frames_dir / f"frame_{i:05d}.png")

            if (i + 1) % 30 == 0 or i == actual_frames - 1:
                pct = (i + 1) / max(actual_frames, 1) * 100
                print(f"  Frame {i + 1}/{actual_frames} ({pct:.0f}%)...")

        # Step 3: Encode processed frames to MP4
        print("  Encoding MP4...")
        encode_cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-framerate", str(output_fps),
            "-i", str(out_frames_dir / "frame_%05d.png"),
            "-c:v", "libx264", "-preset", "medium",
            "-crf", str(CRF), "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output_path)
        ]
        result = subprocess.run(encode_cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  Encode error: {result.stderr[:300]}")
            return None

    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"Done! {actual_frames} frames → {output_path.name} ({size_mb:.1f} MB)")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Composite pottery spinning video onto space background"
    )
    parser.add_argument("--input", required=True, help="Path to raw .mov/.mp4 file")
    parser.add_argument("--planet", required=True, help="Planet name (e.g. Pyr-os-8)")
    parser.add_argument("--output-dir", default=None, help="Output directory")
    args = parser.parse_args()

    result = process_video(args.input, args.planet, args.output_dir)
    if result:
        print(f"\nOutput: {result}")
    else:
        print("\nFailed!")
        sys.exit(1)
