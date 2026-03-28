#!/usr/bin/env python3
"""
UI Sound Design for Ceramics Instagram Videos

Generates programmatic sci-fi UI sounds (numpy → WAV) for the planetary
exploration video frames. Sounds are layered into the final video via ffmpeg.

Sounds:
  - Boot-up hum: Low frequency sweep (100→60Hz) over 0.5s
  - Typing clicks: Short noise bursts at typewriter rhythm
  - Data readout beep: Short sine tone (800Hz, 50ms) on stat completion
  - Border draw: Soft electronic tone when frame borders appear
  - Ambient bed: Very quiet low-frequency pad, fades in and loops
"""

import math
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import List, Tuple, Optional

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

SAMPLE_RATE = 44100


def _generate_wav(samples: 'np.ndarray', output_path: Path) -> Path:
    """Write numpy float array to WAV file."""
    import wave
    # Normalize to 16-bit range
    if np.max(np.abs(samples)) > 0:
        samples = samples / np.max(np.abs(samples)) * 0.8
    int_samples = (samples * 32767).astype(np.int16)
    with wave.open(str(output_path), 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(int_samples.tobytes())
    return output_path


def generate_bootup_hum(duration: float = 0.5, output_path: Optional[Path] = None) -> Path:
    """Low frequency sweep from 100Hz → 60Hz with subtle noise."""
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy required for sound generation")
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='_bootup.wav'))

    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Frequency sweep
    freq = np.linspace(100, 60, len(t))
    phase = 2 * np.pi * np.cumsum(freq) / SAMPLE_RATE
    tone = np.sin(phase) * 0.5
    # Add subtle noise
    noise = np.random.normal(0, 0.05, len(t))
    # Envelope: quick fade in, slow fade out
    envelope = np.ones(len(t))
    fade_in = int(0.02 * SAMPLE_RATE)
    fade_out = int(0.15 * SAMPLE_RATE)
    envelope[:fade_in] = np.linspace(0, 1, fade_in)
    envelope[-fade_out:] = np.linspace(1, 0, fade_out)

    samples = (tone + noise) * envelope
    return _generate_wav(samples, output_path)


def generate_typing_clicks(click_times: List[float], click_duration: float = 0.02,
                           output_path: Optional[Path] = None) -> Path:
    """Generate typing click sounds at specified times (in seconds)."""
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy required for sound generation")
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='_typing.wav'))

    if not click_times:
        # Empty sound file
        return _generate_wav(np.zeros(SAMPLE_RATE), output_path)

    total_duration = max(click_times) + click_duration + 0.1
    total_samples = int(SAMPLE_RATE * total_duration)
    samples = np.zeros(total_samples)

    for t_sec in click_times:
        start = int(t_sec * SAMPLE_RATE)
        length = int(click_duration * SAMPLE_RATE)
        end = min(start + length, total_samples)
        # Short noise burst with fast decay
        click = np.random.normal(0, 0.3, end - start)
        decay = np.exp(-np.linspace(0, 15, end - start))
        samples[start:end] += click * decay

    return _generate_wav(samples, output_path)


def generate_beep(frequency: float = 800, duration: float = 0.05,
                  time_offset: float = 0.0, output_path: Optional[Path] = None) -> Path:
    """Generate a short sine tone beep."""
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy required for sound generation")
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='_beep.wav'))

    # Pad with silence to position the beep at time_offset
    total_duration = time_offset + duration + 0.05
    total_samples = int(SAMPLE_RATE * total_duration)
    samples = np.zeros(total_samples)

    start = int(time_offset * SAMPLE_RATE)
    length = int(duration * SAMPLE_RATE)
    end = min(start + length, total_samples)

    t = np.linspace(0, duration, end - start, endpoint=False)
    tone = np.sin(2 * np.pi * frequency * t) * 0.4
    # Quick envelope
    env = np.ones(end - start)
    if len(env) > 2:
        env[0] = 0
        env[-1] = 0
    samples[start:end] = tone * env

    return _generate_wav(samples, output_path)


def generate_border_tone(duration: float = 0.3, output_path: Optional[Path] = None) -> Path:
    """Soft electronic tone when frame borders appear."""
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy required for sound generation")
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='_border.wav'))

    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Two slightly detuned sine waves for electronic feel
    tone = (np.sin(2 * np.pi * 440 * t) + np.sin(2 * np.pi * 443 * t)) * 0.15
    envelope = np.exp(-t * 5)  # Quick decay
    samples = tone * envelope
    return _generate_wav(samples, output_path)


def generate_ambient_bed(duration: float = 10.0, output_path: Optional[Path] = None) -> Path:
    """Very quiet low-frequency ambient pad that loops."""
    if not NUMPY_AVAILABLE:
        raise RuntimeError("numpy required for sound generation")
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix='_ambient.wav'))

    t = np.linspace(0, duration, int(SAMPLE_RATE * duration), endpoint=False)
    # Layer of low frequency drones
    tone = (
        np.sin(2 * np.pi * 55 * t) * 0.1 +
        np.sin(2 * np.pi * 82.5 * t) * 0.05 +
        np.sin(2 * np.pi * 110 * t) * 0.03
    )
    # Very subtle noise
    noise = np.random.normal(0, 0.01, len(t))
    # Slow fade in over first 2 seconds, fade out over last second
    envelope = np.ones(len(t))
    fade_in = int(2.0 * SAMPLE_RATE)
    fade_out = int(1.0 * SAMPLE_RATE)
    envelope[:fade_in] = np.linspace(0, 1, fade_in)
    envelope[-fade_out:] = np.linspace(1, 0, fade_out)

    samples = (tone + noise) * envelope
    return _generate_wav(samples, output_path)


def generate_all_sounds(output_dir: Path, fps: int = 30,
                        boot_duration: float = 0.5,
                        border_delay_ms: int = 100,
                        typewriter_timing: Optional[List[float]] = None,
                        stat_completion_time: Optional[float] = None) -> dict:
    """
    Generate all UI sounds for a video.

    Args:
        output_dir: Directory to write WAV files into.
        fps: Video frame rate.
        boot_duration: Duration of boot-up sequence in seconds.
        border_delay_ms: Delay in ms before border tone plays.
        typewriter_timing: List of times (seconds) for typing clicks.
        stat_completion_time: Time (seconds) when stat values finish typing.

    Returns:
        Dict mapping sound name to file path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    sounds = {}

    # 1. Boot-up hum
    sounds['bootup'] = generate_bootup_hum(boot_duration, output_dir / 'bootup.wav')

    # 2. Border draw tone (delayed to match visual border appearance)
    sounds['border'] = generate_border_tone(0.3, output_dir / 'border.wav')
    sounds['_border_delay_ms'] = border_delay_ms

    # 3. Typing clicks
    if typewriter_timing:
        sounds['typing'] = generate_typing_clicks(
            typewriter_timing, 0.02, output_dir / 'typing.wav'
        )

    # 4. Data readout beep
    if stat_completion_time:
        sounds['beep'] = generate_beep(800, 0.05, stat_completion_time, output_dir / 'beep.wav')

    # 5. Ambient bed
    sounds['ambient'] = generate_ambient_bed(10.0, output_dir / 'ambient.wav')

    return sounds


def mix_sounds_with_video(video_path: Path, sounds: dict, output_path: Path,
                          total_duration: float) -> Path:
    """
    Mix generated sound files with a video using ffmpeg.

    Args:
        video_path: Path to the silent video.
        sounds: Dict of {name: wav_path} from generate_all_sounds().
        output_path: Path for the final video with audio.
        total_duration: Total video duration in seconds.

    Returns:
        Path to the output video.
    """
    # Build ffmpeg filter complex for mixing multiple audio inputs
    # Input 0 = video, inputs 1..N = WAV files
    inputs = ['-i', str(video_path)]
    filter_parts = []

    audio_idx = 0
    for name, wav_path in sounds.items():
        if not isinstance(wav_path, Path):
            continue
        inputs.extend(['-i', str(wav_path)])
        # WAV audio stream is input index (audio_idx+1), stream a
        in_label = f'{audio_idx + 1}:a'

        # Apply per-sound adjustments
        if name == 'ambient':
            filter_parts.append(f'[{in_label}]apad=pad_dur={total_duration},volume=0.3[ao{audio_idx}]')
        elif name == 'bootup':
            filter_parts.append(f'[{in_label}]apad=pad_dur={total_duration}[ao{audio_idx}]')
        elif name == 'border':
            border_delay = sounds.get('_border_delay_ms', 100)
            filter_parts.append(f'[{in_label}]adelay={border_delay}|{border_delay},apad=pad_dur={total_duration},volume=0.5[ao{audio_idx}]')
        elif name == 'typing':
            typing_end = sounds.get('_typing_end_time')
            if typing_end:
                filter_parts.append(f'[{in_label}]atrim=0:{typing_end},apad=pad_dur={total_duration},volume=0.6[ao{audio_idx}]')
            else:
                filter_parts.append(f'[{in_label}]apad=pad_dur={total_duration},volume=0.6[ao{audio_idx}]')
        elif name == 'beep':
            filter_parts.append(f'[{in_label}]apad=pad_dur={total_duration},volume=0.5[ao{audio_idx}]')
        else:
            filter_parts.append(f'[{in_label}]apad=pad_dur={total_duration}[ao{audio_idx}]')

        audio_idx += 1

    # Mix all audio streams together
    num_audio = audio_idx
    mix_inputs = ''.join(f'[ao{i}]' for i in range(num_audio))
    filter_parts.append(f'{mix_inputs}amix=inputs={num_audio}:duration=first:dropout_transition=3[aout]')

    filter_complex = ';'.join(filter_parts)

    cmd = ['ffmpeg', '-y'] + inputs + [
        '-filter_complex', filter_complex,
        '-map', '0:v',  # Video from first input
        '-map', '[aout]',  # Mixed audio
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',
        str(output_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  Audio mixing error: {result.stderr[-300:]}")
        import shutil
        shutil.copy2(str(video_path), str(output_path))
        print("  Fallback: copied video without audio")

    return output_path
