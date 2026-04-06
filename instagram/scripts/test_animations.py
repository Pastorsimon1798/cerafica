#!/usr/bin/env python3
"""
Quick test for animated frame effects and sound design.
Generates synthetic pottery frames and produces a short test video.
Does NOT interfere with any running frame_video.py process.
"""

import sys
import tempfile
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))

from PIL import Image, ImageDraw
from video_frame_generator import VideoFrameGenerator
from sound_design import generate_all_sounds, mix_sounds_with_video


def generate_synthetic_frames(output_dir: Path, num_frames: int = 90, fps: int = 30):
    """Generate fake pottery frames (spinning colored circle)."""
    output_dir.mkdir(parents=True, exist_ok=True)
    size = (1080, 1350)

    for i in range(num_frames):
        img = Image.new('RGB', size, (30, 30, 40))
        draw = ImageDraw.Draw(img)

        # Simulate a spinning pot - ellipse that shifts horizontally
        cx = size[0] // 2 + int(80 * __import__('math').sin(i * 0.1))
        cy = size[1] // 2
        # Pot body
        draw.ellipse([cx - 200, cy - 300, cx + 200, cy + 300],
                     fill=(180, 120, 80), outline=(140, 90, 60), width=3)
        # Rim highlight
        draw.ellipse([cx - 190, cy - 290, cx + 190, cy - 260],
                     fill=(200, 150, 100))
        # Some surface detail lines
        for j in range(-200, 201, 60):
            x_off = int(20 * __import__('math').sin(i * 0.15 + j * 0.01))
            draw.arc([cx - 180 + x_off, cy + j - 20, cx + 180 + x_off, cy + j + 20],
                     0, 180, fill=(160, 100, 60), width=2)

        img.save(output_dir / f"frame_{i + 1:06d}.png")

    return num_frames


def main():
    print("=== Animated Frame Effects Test ===\n")

    # Fake planet data with all fields to exercise typewriter
    planet_data = {
        "planet_name": "Test-Planet-7",
        "lore": "Discovered in the Outer Rim, this celestial body exhibits unusual crystalline formations. Its surface is composed of layered sedimentary deposits.",
        "surface_geology": "Crystalline basalt with iron oxide deposits",
        "origin": "Volcanic eruption, slow cooling",
        "firing_state": "Cone 10 reduction",
        "chemistry": "SiO2 65% | Al2O3 20% | Fe2O3 8%",
        "anomalies": "Unusual copper oxide flashing on southern hemisphere",
        "clay_type": "stoneware_with_grog",
    }

    with tempfile.TemporaryDirectory(prefix="test_animations_") as tmpdir:
        tmpdir = Path(tmpdir)
        frames_dir = tmpdir / "frames"
        processed_dir = tmpdir / "processed"
        sounds_dir = tmpdir / "sounds"
        output_dir = Path(__file__).parent.parent.parent / "output" / "test_export"
        output_dir.mkdir(parents=True, exist_ok=True)

        fps = 30
        num_frames = 180  # 6 seconds — enough time to see full animation + hold

        # Step 1: Generate synthetic frames
        print(f"1. Generating {num_frames} synthetic frames...")
        generate_synthetic_frames(frames_dir, num_frames, fps)

        # Step 2: Process with animated generator
        print("2. Processing with animated HUD...")
        import time
        generator = VideoFrameGenerator(planet_data, seed=42, zoom=1.0, animate=True)
        # Skip rembg for speed — test frames don't need background removal (~7s/frame saved)
        generator.rembg_session = None
        processed_dir.mkdir()

        t0 = time.time()
        for i in range(num_frames):
            frame = Image.open(frames_dir / f"frame_{i + 1:06d}.png")
            processed = generator.process_frame(frame, frame_index=i, total_frames=num_frames)
            processed.save(processed_dir / f"frame_{i + 1:06d}.png")
            pct = (i + 1) / num_frames
            sys.stdout.write(f"\r   [{i + 1}/{num_frames}] {pct:.0%}")
            sys.stdout.flush()
        sys.stdout.write("\n")
        elapsed = time.time() - t0
        print(f"   {elapsed:.1f}s total ({num_frames / elapsed:.1f} f/s)")

        # Step 3: Assemble video (no crossfade for short test)
        video_path = output_dir / "test_animated.mp4"
        print("3. Assembling video...", end=" ", flush=True)
        subprocess.run([
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-start_number', '1',
            '-i', str(processed_dir / 'frame_%06d.png'),
            '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
            str(video_path),
        ], capture_output=True, check=True)
        print("done")

        # Step 4: Generate and mix sounds
        # Sync timings to match animation engine's pacing
        print("4. Generating UI sounds...")
        boot_budget = max(30, int(num_frames * 0.20))  # Same formula as _get_boot_timing
        boot_duration = boot_budget / fps
        text_start = boot_duration  # Text begins after boot-up
        lore_len = len(planet_data.get('lore', ''))
        lore_duration = lore_len / 1.0  # 1 char per frame at 30fps
        stats_start = text_start + lore_duration + (8 / fps)  # +8 frame pause
        stat_value_start = stats_start + (15 / fps)
        # Typing clicks: one every 1/30s (1 char per frame)
        click_times = [text_start + i / fps for i in range(int(lore_duration * fps))]
        # Beep when stat values start appearing
        stat_completion_time = stat_value_start

        sounds = generate_all_sounds(
            sounds_dir, fps=fps,
            boot_duration=boot_duration,
            typewriter_timing=click_times,
            stat_completion_time=stat_completion_time,
        )
        for name, path in sounds.items():
            sz = path.stat().st_size
            print(f"   {name}: {sz:,} bytes")

        final_path = output_dir / "test_animated_with_audio.mp4"
        print("5. Mixing audio...", end=" ", flush=True)
        video_duration = num_frames / fps
        mix_sounds_with_video(video_path, sounds, final_path, video_duration)
        print("done")

        # Step 5: Also generate a static version for comparison
        print("6. Generating static (no-animate) version for comparison...")
        generator_static = VideoFrameGenerator(planet_data, seed=42, zoom=1.0, animate=False)
        generator_static.rembg_session = None
        processed_static = tmpdir / "processed_static"
        processed_static.mkdir()
        for i in range(num_frames):
            frame = Image.open(frames_dir / f"frame_{i + 1:06d}.png")
            processed = generator_static.process_frame(frame)
            processed.save(processed_static / f"frame_{i + 1:06d}.png")

        static_path = output_dir / "test_static.mp4"
        subprocess.run([
            'ffmpeg', '-y',
            '-framerate', str(fps),
            '-start_number', '1',
            '-i', str(processed_static / 'frame_%06d.png'),
            '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
            str(static_path),
        ], capture_output=True, check=True)

        print("\n=== DONE ===")
        print("\nOutput files:")
        print(f"  Animated + audio: {final_path}")
        print(f"  Animated (no audio): {video_path}")
        print(f"  Static (comparison): {static_path}")
        print("\nOpen with:")
        print(f"  open \"{final_path}\"")


if __name__ == "__main__":
    main()
