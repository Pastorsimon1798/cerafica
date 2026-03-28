# Pipeline Architecture Redesign: frame_video.py

**Date:** 2026-03-22
**Status:** Approved

## Problem

The frame_video.py pipeline takes 50+ minutes for a 4-second loop due to three architectural mistakes:

1. **4K footage discarded at extraction** — frames downscaled to 1080px before any processing
2. **rembg runs on full frames** — processes background pixels that are immediately thrown away
3. **COMPOSITE_SCALE=2 fake resolution** — upscales already-downscaled data to 2x then back, adding no real detail

## Design

### Resolution Strategy

| Stage | Resolution | Why |
|---|---|---|
| Source video | 4K (3840x2160, iPhone) | Native capture quality |
| Frame extraction | 2K (1080x1920 portrait) | Sharp enough for 1080px output, 4x fewer pixels than 4K |
| Loop detection | 360px thumbnails | Already implemented, works well |
| rembg input | Pottery crop only (~40% of frame) | Biggest speedup: rembg on ~0.8M px instead of 2.1M px |
| Compositing | 1080x1920 directly | No fake 2x upscale/downscale |
| HUD/effects | 1080x1920 | Same as output |
| Final output | 1080x1920, H.264, 30fps | Full 9:16 Instagram Reel |

### Pipeline Flow

```
Phase 0: Extract + Detect
  ffmpeg extract at 2K (1080px wide)
  Loop detection on 360px thumbnails (edge-based MSE, threshold 2500)
  → 241 frames for IMG_4967 (4.0s loop)

Phase 1: Masks (crop-first)
  1a. For first frame: detect pottery bbox, crop, run rembg on crop
  1b. For remaining keyframes (every 3rd): rembg on same crop region
  1c. Interpolate intermediate masks
  → ~16 min for 81 keyframes (down from 50+ min)

Phase 2: Composite (no fake upscale)
  Crop pottery from raw frame using bbox
  Scale crop to fit 1080x1920 art area
  Composite onto space background at 1080x1920
  Add glow, rim light, zoom panels at 1080x1920
  → ~15-20 min for 241 frames

Phase 3: HUD
  Animated overlay at 1080x1920 (typewriter, boot-up, scan lines)
  → ~5-10 min for 241 frames

Phase 4: Assemble + Sound
  ffmpeg encode + crossfade loop
  Sound design (typewriter clicks, boot hum, border sweep)
  → ~2 min

Total estimated: ~40-50 min (down from 2+ hours)
```

### Key Changes

1. **`extract_frames()`**: Change `max_width=1080` to `max_width=1080` (already 2K portrait after auto-rotate from 2160px wide 4K). Actually, the 4K source is 3840x2160 landscape, auto-rotated to 2160x3840 portrait. `scale=1080:-2` gives 1080x1920 which IS 2K portrait. No change needed here.

2. **`extract_mask()`**: Crop to pottery bbox BEFORE running rembg, not after. This is the biggest change. Currently rembg processes the full 1080x1920 frame. With crop-first, it processes only the ~600x800 pottery region.

3. **`COMPOSITE_SCALE=2` → `COMPOSITE_SCALE=1`**: Remove the 2x upscale/downscale. Composite directly at 1080x1920. The "sharpness" benefit was from fake resolution — the source data is already 1080px, upscaling it adds nothing.

4. **`VIDEO_HEIGHT`**: Change from 1350 to 1920 for full 9:16 Reel format.

5. **Loop detection**: Already fixed (edge-based MSE, threshold 2500).

6. **Frame extraction**: Already fixed (removed broken transpose, fixed scale quoting).

### Files Changed

- `instagram/scripts/frame_video.py` — extraction params, loop detection (done)
- `instagram/scripts/lib/video_frame_generator.py` — COMPOSITE_SCALE, VIDEO_HEIGHT, extract_mask crop-first, composite at 1x
