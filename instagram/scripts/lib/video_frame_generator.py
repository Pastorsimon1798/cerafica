#!/usr/bin/env python3
"""
Video Frame Generator for Ceramics Instagram

Processes individual video frames with the planetary exploration frame overlay.
Designed for pottery spinning on a banding wheel — each frame gets:
  1. Background removal (rembg)
  2. Space background composite (with twinkling stars)
  3. Center glow (sampled from frame)
  4. Rim light on pottery edges
  5. Animated HUD overlay (typewriter text, boot-up, pulsing corners, drifting scan lines)

Key differences from static frame generator:
  - Processes at 1x (1080x1350) instead of 2x (2160x2700)
  - Zoom panels use cached regions from frame 0 (no jumping)
  - Pre-computes all static assets (fonts, logo, space bg)
  - Per-frame: bg removal, accent color, glow, rim light, zoom panels, animated HUD
"""

import io
import math
import random
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps, ImageChops

from frame_generator import (
    SpaceBackground,
    COLORS,
    HEADER_HEIGHT,
    FOOTER_HEIGHT,
    MARGIN,
    LOGO_PATH,
    _find_font,
    wrap_text,
    REMBG_AVAILABLE,
)

try:
    from rembg import new_session, remove
except ImportError:
    REMBG_AVAILABLE = False

# Video output resolution (9:16 Instagram Reel)
VIDEO_WIDTH = 1080
VIDEO_HEIGHT = 1920
COMPOSITE_SCALE = 1  # Composite at output resolution — no fake upscale

# Animation timing (in frames, assuming ~30fps output)
# These are base values — the animation engine scales them to video length
BOOT_DURATION_FRAMES = 30       # 1.0s at 30fps — HUD elements fade in
TYPEWRITER_CHARS_PER_FRAME = 1  # 1 char per frame = 30 chars/sec (human reading pace)


class VideoFrameGenerator:
    """
    Processes individual video frames with planetary exploration overlay.

    Static assets (space bg, fonts, logo, rembg session, star layers) are
    computed once at init. Per-frame processing includes:
    - Background removal
    - Piece scaling and compositing
    - Accent color sampling + center glow
    - Rim light edge detection
    - Animated HUD overlay (when animate=True)
    """

    def __init__(self, planet_data: Dict[str, Any], seed: int = 42, zoom: float = 1.05,
                 animate: bool = True,
                 photo_zoom_panels: Optional[List[Image.Image]] = None,
                 photo_zoom_labels: Optional[List[str]] = None):
        self.planet_data = planet_data
        self.zoom = zoom  # Piece fill ratio (1.0 = fill art area, 1.2 = overflow 20%)
        self.animate = animate
        random.seed(seed)
        self._seed = seed

        # Pre-computed zoom panels from a framed photo (for re-HUD mode)
        self._photo_zoom_panels: Optional[List[Image.Image]] = photo_zoom_panels
        self._photo_zoom_labels: List[str] = photo_zoom_labels or [f"ZOOM-{i+1}" for i in range(len(photo_zoom_panels or []))]

        # --- Pre-compute static assets ---

        # rembg session (reused across all frames for speed)
        self.rembg_session = None
        if REMBG_AVAILABLE:
            try:
                self.rembg_session = new_session(model_name='birefnet-general')
            except Exception:
                pass

        # Fonts
        self.font_header = _find_font(28, bold=True)
        self.font_data = _find_font(18)
        self.font_small = _find_font(14)
        self.font_label = _find_font(13)
        self.font_value = _find_font(17)
        self.font_lore = _find_font(15)

        # Logo (load and scale once)
        self.logo = None
        if LOGO_PATH.exists():
            logo = Image.open(LOGO_PATH).convert('RGBA')
            target_h = 120  # Half the static size for 1x resolution
            ratio = target_h / logo.height
            logo_w = int(logo.width * ratio)
            self.logo = logo.resize((logo_w, target_h), Image.Resampling.LANCZOS)

        # Space background base with static stars baked in (no twinkling)
        accent_color = None
        self.space_bg_base = SpaceBackground(
            VIDEO_WIDTH, VIDEO_HEIGHT, seed=seed, accent_color=accent_color
        )._generate_base()  # bg + nebula + vignette + scan lines, no stars

        # Bake one static star layer into the base
        static_stars = SpaceBackground.generate_star_layer(VIDEO_WIDTH, VIDEO_HEIGHT, seed)
        self.space_bg_base = Image.alpha_composite(self.space_bg_base.convert('RGBA'), static_stars)

        self.star_layers: List[Image.Image] = []

        # Pre-compute text elements for typewriter animation
        self._text_elements = self._compute_text_elements()

        # Static HUD overlay (used when animate=False)
        if not self.animate:
            self.hud_overlay = self._build_hud_overlay()

        # Reference crop from first frame — fixed crop window prevents jitter
        # Set during first extract_mask() call, reused for crop-before-rembg
        self._ref_crop = None
        self._rembg_crop_initialized = False
        # Reference size from first frame — locks piece dimensions across all frames
        self._ref_size = None
        # Cached zoom regions from frame 0 (reused for all frames)
        self._zoom_regions = None

        # Cached overlays (generated from frame 0, reused for all frames)
        self._cached_glow: Optional[Image.Image] = None
        self._cached_rim: Optional[Image.Image] = None
        self._cached_rim_bbox: Optional[Tuple[int, int, int, int]] = None

        # HUD static layer (split rendering optimization)
        self._hud_static_layer: Optional[Image.Image] = None

    def _compute_text_elements(self) -> Dict[str, Any]:
        """Pre-compute all text content for typewriter animation."""
        pd = self.planet_data
        planet_name = pd.get('planet_name') or ''
        lore = pd.get('lore') or ''

        # Build lore lines
        dummy_draw = ImageDraw.Draw(Image.new('RGBA', (1, 1)))
        lore_lines = wrap_text(str(lore), self.font_lore, VIDEO_WIDTH - 2 * (MARGIN // 2), dummy_draw)[:3]
        lore_full = ' '.join(lore_lines)

        # Build stat entries: (label, value_str, column)
        stats = []

        surface = pd.get('surface_qualities') or pd.get('surface_geology') or 'Unknown'
        surface_lines = wrap_text(str(surface)[:60], self.font_value, 400, dummy_draw)[:1]
        stats.append(('SURFACE', ' '.join(surface_lines), 'left'))

        origin = pd.get('origin')
        if origin:
            origin_lines = wrap_text(str(origin)[:50], self.font_value, 400, dummy_draw)[:1]
            stats.append(('ORIGIN', ' '.join(origin_lines), 'left'))

        firing = pd.get('firing_state')
        if firing and firing not in ['work in progress', 'work_in_progress', None]:
            firing_lines = wrap_text(str(firing), self.font_value, 400, dummy_draw)[:1]
            stats.append(('FIRING STATE', ' '.join(firing_lines), 'left'))

        chemistry = pd.get('chemistry')
        if chemistry:
            compounds = [c.strip() for c in str(chemistry).split('|')]
            stats.append(('COMPOSITION', str(chemistry), 'right'))

        anomalies = pd.get('anomalies')
        if anomalies:
            anom_lines = wrap_text(str(anomalies)[:100], self.font_value, 400, dummy_draw)[:2]
            stats.append(('ANOMALIES', ' '.join(anom_lines), 'right'))

        clay = pd.get('clay_type')
        if clay:
            clay_lines = wrap_text(str(clay).replace('_', ' ').title(), self.font_value, 400, dummy_draw)[:1]
            stats.append(('SUBSTRATE', ' '.join(clay_lines), 'right'))

        return {
            'planet_name': planet_name.title() if planet_name else '',
            'lore': lore_full,
            'stats': stats,
        }

    def _compute_typewriter_speed(self, total_frames: int) -> int:
        """Adaptive typewriter speed: chars per frame, scaled so text finishes before video ends."""
        te = self._text_elements
        bt = self._get_boot_timing(total_frames)
        text_start = bt['text_start']

        # Total chars to type across all phases
        lore_chars = len(te.get('lore', ''))
        label_chars = sum(len(label) for label, value, col in te.get('stats', []))
        value_chars = sum(len(value) for label, value, col in te.get('stats', []))

        # Phases: lore -> 8-frame pause -> labels -> 15-frame pause -> values
        total_typing_chars = lore_chars + label_chars + value_chars
        total_pause_frames = 8 + 15
        available_frames = total_frames - text_start - total_pause_frames

        if available_frames <= 0 or total_typing_chars <= 0:
            return TYPEWRITER_CHARS_PER_FRAME  # fallback to default

        # Speed = how many chars per frame to fit all text with a small buffer
        speed = max(1, math.ceil(total_typing_chars / available_frames))

        return min(speed, 5)  # cap at 5 chars/frame (still looks like typing)

    def _typewriter_count(self, frame_index: int, start_frame: int, total_chars: int,
                          chars_per_frame: int = TYPEWRITER_CHARS_PER_FRAME) -> int:
        """Calculate how many characters to show for typewriter effect."""
        if frame_index < start_frame:
            return 0
        elapsed = frame_index - start_frame
        chars = elapsed * chars_per_frame
        return min(chars, total_chars)

    def _get_boot_timing(self, total_frames: int) -> Dict[str, int]:
        """Calculate boot-up sequence timing scaled to video length.

        Returns dict with start/end frames for each element.
        Short videos (<3s) get compressed timing. Longer videos get cinematic pacing.
        When _no_boot_fade is True, all elements appear instantly but text_start
        is preserved for typewriter animation.
        """
        if getattr(self, '_no_boot_fade', False):
            return {
                'header_start': 0, 'header_fade': 0,
                'borders_start': 0, 'borders_fade': 0,
                'corners_start': 0, 'corners_fade': 0,
                'footer_start': 0, 'footer_fade': 0,
                'text_start': 5,
            }

        # Boot-up takes ~20% of video, capped at 2s (60 frames at 30fps)
        boot_budget = max(BOOT_DURATION_FRAMES, int(total_frames * 0.20))
        boot_budget = min(boot_budget, 60)  # Cap at 2s

        # Stagger elements across the boot budget
        # Each element fades in over ~40% of the boot budget
        fade_dur = max(8, int(boot_budget * 0.4))

        return {
            'header_start': 0,
            'header_fade': fade_dur,
            'borders_start': max(5, int(boot_budget * 0.15)),
            'borders_fade': fade_dur,
            'corners_start': max(10, int(boot_budget * 0.30)),
            'corners_fade': fade_dur,
            'footer_start': max(15, int(boot_budget * 0.45)),
            'footer_fade': fade_dur,
            'text_start': boot_budget,  # Text begins after all elements are in
        }

    def _fade_alpha(self, frame_index: int, start_frame: int, duration: int) -> float:
        """Calculate fade-in alpha (0.0 → 1.0) for boot-up elements."""
        if frame_index < start_frame:
            return 0.0
        if frame_index >= start_frame + duration:
            return 1.0
        return (frame_index - start_frame) / duration

    def _build_hud_overlay(self, frame_index: int = 0, total_frames: int = 1) -> Image.Image:
        """
        Render the full HUD overlay as an RGBA image.

        When animate=True, applies per-frame animation effects:
        - Boot-up sequence (elements fade/slide in during first N frames)
        - Typewriter text reveal
        - Drifting scan lines
        - Pulsing corner brackets
        - Twinkling stars
        """
        hud = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(hud)

        planet_data = self.planet_data
        te = self._text_elements

        # Boot-up sequence timing (scaled to video length)
        if self.animate:
            bt = self._get_boot_timing(total_frames)
            header_start = bt['header_start']
            header_fade = bt['header_fade']
            borders_start = bt['borders_start']
            borders_fade = bt['borders_fade']
            corners_start = bt['corners_start']
            corners_fade = bt['corners_fade']
            footer_start = bt['footer_start']
            footer_fade = bt['footer_fade']
            text_start = bt['text_start']
            tw_speed = self._compute_typewriter_speed(total_frames)
        else:
            header_start = header_fade = 0
            borders_start = borders_fade = 0
            corners_start = corners_fade = 0
            footer_start = footer_fade = 0
            text_start = 0

        header_alpha = self._fade_alpha(frame_index, header_start, header_fade) if self.animate else 1.0
        borders_alpha = self._fade_alpha(frame_index, borders_start, borders_fade) if self.animate else 1.0
        corners_alpha = self._fade_alpha(frame_index, corners_start, corners_fade) if self.animate else 1.0
        footer_alpha = self._fade_alpha(frame_index, footer_start, footer_fade) if self.animate else 1.0

        # ========== HEADER BAR ==========
        header_h = HEADER_HEIGHT // 2
        if header_alpha > 0:
            header_fill_alpha = int(200 * header_alpha)
            draw.rectangle([0, 0, VIDEO_WIDTH, header_h], fill=(0, 0, 0, header_fill_alpha))

            # Header text — planet name (typewriter during boot-up, then static)
            if self.animate:
                name_chars = self._typewriter_count(frame_index, 0, len("Cerafica Exploration Log"))
                header_text = "Cerafica Exploration Log"[:name_chars]
                # Blinking cursor
                if name_chars < len("Cerafica Exploration Log"):
                    cursor_char = "_" if (frame_index % 6) < 3 else " "
                else:
                    cursor_char = ""
                draw.text((MARGIN // 2, 12), header_text + cursor_char,
                          font=self.font_header, fill=COLORS["cyan_glow"])

                if te['planet_name']:
                    planet_chars = self._typewriter_count(frame_index, 0, len(te['planet_name']))
                    planet_text = te['planet_name'][:planet_chars]
                    planet_w = int(self.font_header.getlength(planet_text))
                    draw.text((VIDEO_WIDTH - MARGIN // 2 - planet_w, 12),
                              planet_text, font=self.font_header, fill=COLORS["cyan_glow"])
            else:
                draw.text((MARGIN // 2, 12), "Cerafica Exploration Log",
                          font=self.font_header, fill=COLORS["cyan_glow"])
                if te['planet_name']:
                    name_w = int(self.font_header.getlength(te['planet_name']))
                    draw.text((VIDEO_WIDTH - MARGIN // 2 - name_w, 12),
                              te['planet_name'], font=self.font_header, fill=COLORS["cyan_glow"])

            # Header line
            line_alpha = int(255 * header_alpha)
            draw.line([(0, header_h), (VIDEO_WIDTH, header_h)],
                      fill=(*COLORS["white_soft"][:3], line_alpha), width=1)

        # ========== FOOTER ==========
        footer_h = FOOTER_HEIGHT // 2
        footer_y = VIDEO_HEIGHT - footer_h

        if footer_alpha > 0:
            footer_fill_alpha = int(220 * footer_alpha)
            draw.rectangle([0, footer_y, VIDEO_WIDTH, VIDEO_HEIGHT], fill=(0, 0, 0, footer_fill_alpha))

            # Footer top border
            border_line_alpha = int(200 * footer_alpha)
            draw.line([(0, footer_y), (VIDEO_WIDTH, footer_y)],
                      fill=(*COLORS["cyan_glow"], border_line_alpha), width=2)

            # --- 1. Lore quote (typewriter) ---
            y = footer_y + 10
            if self.animate and te['lore']:
                lore_chars = self._typewriter_count(frame_index, text_start, len(te['lore']), chars_per_frame=tw_speed)
                lore_visible = te['lore'][:lore_chars]
                # Wrap the visible portion
                lines = wrap_text(lore_visible, self.font_lore, VIDEO_WIDTH - 2 * (MARGIN // 2), draw)
                for line in lines[:3]:
                    text_alpha = int(180 * footer_alpha)
                    draw.text((MARGIN // 2, y), line,
                              font=self.font_lore, fill=(*COLORS["white_soft"], text_alpha))
                    y += 20
                # Blinking cursor at end of last visible line
                if lore_chars < len(te['lore']) and lines:
                    last_line = lines[-1] if lines else ""
                    cursor_x = MARGIN // 2 + int(self.font_lore.getlength(last_line))
                    if (frame_index % 6) < 3:
                        draw.text((cursor_x, y - 20), "_",
                                  font=self.font_lore, fill=(*COLORS["white_soft"], text_alpha))
            elif te['lore']:
                lines = wrap_text(str(te['lore']), self.font_lore, VIDEO_WIDTH - 2 * (MARGIN // 2), draw)
                for line in lines[:3]:
                    draw.text((MARGIN // 2, y), line,
                              font=self.font_lore, fill=(*COLORS["white_soft"], 180))
                    y += 20
            else:
                lore = planet_data.get('lore')
                if lore:
                    lines = wrap_text(str(lore), self.font_lore, VIDEO_WIDTH - 2 * (MARGIN // 2), draw)
                    for line in lines[:3]:
                        draw.text((MARGIN // 2, y), line,
                                  font=self.font_lore, fill=(*COLORS["white_soft"], 180))
                        y += 20
            y += 4

            # --- 2. Cyan divider ---
            draw.line([(MARGIN // 2, y), (VIDEO_WIDTH - MARGIN // 2, y)],
                      fill=(*COLORS["cyan_glow"], int(120 * footer_alpha)), width=1)
            y += 20

            # --- 3. Two-column stats (typewriter: labels first, then values) ---
            col_width = (VIDEO_WIDTH - 3 * (MARGIN // 2)) // 2
            right_x = MARGIN + col_width

            # LEFT COLUMN
            ly = y
            ry = y

            # Stats start AFTER lore finishes typing, with a short pause
            lore_char_count = len(te['lore']) if te['lore'] else 0
            lore_frames = math.ceil(lore_char_count / tw_speed) if tw_speed > 0 else 0
            stats_label_start = text_start + lore_frames + 8  # 8-frame pause after lore
            stats_value_start = stats_label_start + 15  # Values begin 15 frames after labels

            label_chars_budget = self._typewriter_count(frame_index, stats_label_start, 100, chars_per_frame=tw_speed) if self.animate else 100
            value_chars_budget = self._typewriter_count(frame_index, stats_value_start, 200, chars_per_frame=tw_speed) if self.animate else 200

            left_stats = [s for s in te['stats'] if s[2] == 'left']
            right_stats = [s for s in te['stats'] if s[2] == 'right']

            for label, value, col in te['stats']:
                if col == 'left':
                    stat_x = MARGIN // 2
                    cur_y = ly
                else:
                    stat_x = right_x
                    cur_y = ry

                if self.animate:
                    # Labels type in at normal speed
                    visible_label_len = min(len(label), label_chars_budget)
                    visible_label = label[:visible_label_len]
                    label_color = COLORS["cyan_dim"] if col == 'left' else COLORS["amber"]
                    draw.text((stat_x, cur_y), visible_label,
                              font=self.font_label, fill=label_color)
                    cur_y += 15

                    # Values appear after their label is fully visible
                    if visible_label_len >= len(label):
                        visible_val_len = min(len(value), value_chars_budget)
                        visible_val = value[:visible_val_len]
                        val_color = COLORS["cyan_glow"] if col == 'left' else COLORS["amber"]
                        if label == 'COMPOSITION':
                            compounds = [c.strip() for c in visible_val.split('|') if c.strip()]
                            for compound in compounds:
                                draw.text((stat_x, cur_y), compound, font=self.font_value, fill=val_color)
                                cur_y += 22
                        else:
                            lines = wrap_text(visible_val, self.font_value, col_width - 10, draw)
                            for line in lines[:1]:
                                draw.text((stat_x, cur_y), line, font=self.font_value, fill=val_color)
                                cur_y += 22
                else:
                    label_color = COLORS["cyan_dim"] if col == 'left' else COLORS["amber"]
                    val_color = COLORS["cyan_glow"] if col == 'left' else COLORS["amber"]
                    draw.text((stat_x, cur_y), label, font=self.font_label, fill=label_color)
                    cur_y += 15
                    if label == 'COMPOSITION':
                        compounds = [c.strip() for c in value.split('|') if c.strip()]
                        for compound in compounds:
                            draw.text((stat_x, cur_y), compound, font=self.font_value, fill=val_color)
                            cur_y += 22
                    else:
                        lines = wrap_text(value, self.font_value, col_width - 10, draw)
                        for line in lines[:1]:
                            draw.text((stat_x, cur_y), line, font=self.font_value, fill=val_color)
                            cur_y += 22

                if col == 'left':
                    ly = cur_y
                else:
                    ry = cur_y

        # --- 4. Logo (fades in with footer) ---
        if self.logo and footer_alpha > 0:
            border_pad = 12
            art_bottom = footer_y - border_pad
            art_right = VIDEO_WIDTH - border_pad
            logo_x = art_right - self.logo.width - 5
            logo_y = art_bottom - self.logo.height - 5
            logo_with_alpha = Image.new('RGBA', self.logo.size, (0, 0, 0, 0))
            logo_with_alpha.alpha_composite(self.logo)
            logo_with_alpha.putalpha(
                self.logo.getchannel('A').point(lambda a: int(a * footer_alpha))
            )
            hud.paste(logo_with_alpha, (logo_x, logo_y), logo_with_alpha)
        elif not self.logo and footer_alpha > 0:
            brand_text = "CERAFICA"
            brand_font = _find_font(19, bold=True)
            brand_x = (VIDEO_WIDTH - len(brand_text) * 12) // 2
            draw.text((brand_x, VIDEO_HEIGHT - 40),
                      f"\u25C8 {brand_text} \u25C8", font=brand_font, fill=COLORS["amber"])

        # ========== CARD FRAME BORDERS ==========
        border_pad = 12
        art_top = header_h + border_pad
        art_bottom = footer_y - border_pad
        art_left = border_pad
        art_right = VIDEO_WIDTH - border_pad

        if borders_alpha > 0:
            draw.rectangle(
                [art_left, art_top, art_right, art_bottom],
                outline=(*COLORS["cyan_dim"], int(160 * borders_alpha)), width=1
            )

        # Corner brackets (pulsing when animated)
        if corners_alpha > 0:
            if self.animate:
                # Pulsing: alpha and length vary with sin wave
                pulse = 0.7 + 0.3 * math.sin(frame_index * 0.08)
                cs = int(10 + 4 * (0.5 + 0.5 * math.sin(frame_index * 0.05)))
                corner_alpha = pulse * corners_alpha
            else:
                cs = 12
                corner_alpha = 1.0

            for (cx, cy, dx1, dy1, dx2, dy2) in [
                (art_left, art_top, 1, 0, 0, 1),
                (art_right, art_top, -1, 0, 0, 1),
                (art_left, art_bottom, 1, 0, 0, -1),
                (art_right, art_bottom, -1, 0, 0, -1),
            ]:
                r, g, b = COLORS["cyan_glow"]
                a = int(255 * corner_alpha)
                draw.line([(cx, cy), (cx + cs * dx1, cy)], fill=(r, g, b, a), width=2)
                draw.line([(cx, cy), (cx, cy + cs * dy1)], fill=(r, g, b, a), width=2)

        # ========== SCAN LINES (drifting when animated) ==========
        if self.animate:
            # Offset scan lines by frame_index for drifting effect
            scan_offset = frame_index % 4
        else:
            scan_offset = 0

        for sy in range(scan_offset, header_h, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))
        for sy in range(footer_y + scan_offset, VIDEO_HEIGHT, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))

        return hud

    def _build_star_composite(self, frame_index: int) -> Image.Image:
        """Blend star layers for twinkling effect using PIL blend (faster than numpy float32)."""
        if not self.star_layers:
            return self.space_bg_base

        num_layers = len(self.star_layers)
        cycle_period = 20

        phase = (frame_index % (cycle_period * num_layers)) / cycle_period
        layer_a_idx = int(phase) % num_layers
        layer_b_idx = (layer_a_idx + 1) % num_layers
        blend = phase - int(phase)

        blend = 0.5 - 0.5 * math.cos(blend * math.pi)

        layer_a = self.star_layers[layer_a_idx]
        layer_b = self.star_layers[layer_b_idx]

        return Image.blend(layer_a, layer_b, blend)

    @staticmethod
    def extract_zoom_panels_from_photo(photo_path: str) -> List[Image.Image]:
        """Extract zoom panel regions from a 2x framed photo and downscale to 1x.

        Crops the 3 zoom panel regions from known 2x coordinates:
          Panel 0: (1820, 130, 2120, 430)  — 300x300
          Panel 1: (1820, 466, 2120, 766)  — 300x300
          Panel 2: (1820, 802, 2120, 1102) — 300x300

        Returns list of 150x150 RGBA images.
        """
        photo = Image.open(photo_path).convert('RGBA')
        # 2x coordinates from frame_generator.py: panel_width=300, sidebar_x=1820, start_y=130
        panel_coords_2x = [
            (1820, 130, 2120, 430),
            (1820, 466, 2120, 766),
            (1820, 802, 2120, 1102),
        ]
        target_size = 150  # 1x video resolution panel size
        panels = []
        for x1, y1, x2, y2 in panel_coords_2x:
            crop = photo.crop((x1, y1, x2, y2)).resize(
                (target_size, target_size), Image.Resampling.LANCZOS
            )
            panels.append(crop)
        photo.close()
        return panels

    def apply_hud_only(self, frame_image: Image.Image, frame_index: int = 0,
                       total_frames: int = 1, re_hud: bool = False) -> Image.Image:
        """Apply animated HUD to an already-framed video frame. No rembg/glow/rim.

        Args:
            re_hud: When True, skip boot-up fade-in (all elements at full alpha from frame 0).
                Used when re-applying HUD to a video that already has it baked in,
                to avoid double-layer flickering while ensuring all text is visible.
        """
        canvas = frame_image.convert('RGBA')
        if re_hud:
            # Full HUD but no boot-up fade — covers old baked-in HUD cleanly
            hud = self._build_hud_overlay_no_boot(frame_index, total_frames)
        else:
            hud = self._build_hud_overlay(frame_index, total_frames)
        canvas = Image.alpha_composite(canvas, hud)

        # Composite pre-computed zoom panels with sequential reveal
        if self._photo_zoom_panels:
            canvas = self._composite_photo_zoom_panels(canvas, frame_index, total_frames)

        return canvas.convert('RGB')

    def _build_hud_overlay_no_boot(self, frame_index: int, total_frames: int) -> Image.Image:
        """HUD overlay with instant element appearance but typewriter text reveal.

        Used in re-HUD mode to cleanly cover the old baked-in HUD without
        the fade-in animation that would cause double-layer flickering.
        All structural elements appear at full alpha from frame 0.
        Text still uses typewriter animation (needed for sound sync).
        """
        self._no_boot_fade = True
        try:
            result = self._build_hud_overlay(frame_index, total_frames)
        finally:
            self._no_boot_fade = False
        return result

    def _composite_photo_zoom_panels(self, canvas: Image.Image, frame_index: int,
                                     total_frames: int) -> Image.Image:
        """Overlay zoom panels from a framed photo with sequential fade-in reveal."""
        panel_width = 150
        panel_border = 2
        panel_gap = 18

        header_h = HEADER_HEIGHT // 2
        sidebar_x = VIDEO_WIDTH - panel_width - MARGIN
        start_y = header_h + 20

        # Reveal schedule: each panel starts at a different % of video
        reveal_offsets = [0.15, 0.35, 0.55]
        fade_frames = 15  # ~0.5s at 30fps

        overlay = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        font_label = _find_font(14)

        for i, panel_img in enumerate(self._photo_zoom_panels):
            if i >= len(reveal_offsets):
                break

            start_frame = int(total_frames * reveal_offsets[i])

            if frame_index < start_frame:
                continue  # Not visible yet

            # Compute fade-in alpha
            elapsed = frame_index - start_frame
            alpha = min(255, elapsed * (255 // fade_frames))

            py = start_y + i * (panel_width + panel_gap)

            # Draw border rect with fade alpha
            draw.rectangle(
                [sidebar_x - panel_border, py - panel_border,
                 sidebar_x + panel_width + panel_border, py + panel_width + panel_border],
                fill=(*COLORS["cyan_dim"], int(180 * alpha / 255))
            )

            # Paste panel image with fade alpha
            panel_rgba = panel_img.copy()
            panel_rgba.putalpha(Image.new('L', panel_rgba.size, alpha))
            overlay.paste(panel_rgba, (sidebar_x, py))

            # Draw label with fade alpha
            label = self._photo_zoom_labels[i] if i < len(self._photo_zoom_labels) else f"ZOOM-{i + 1}"
            draw.text((sidebar_x + 4, py - panel_border - 20), label,
                      font=font_label, fill=(*COLORS["cyan_glow"], int(200 * alpha / 255)))

        return Image.alpha_composite(canvas, overlay)

    def extract_mask(self, frame_image: Image.Image) -> Image.Image:
        """
        Phase 1: Extract alpha mask from a raw frame (rembg + cleanup).

        First frame: runs rembg on full image to detect pottery bbox.
        Subsequent frames: crops to bbox before rembg (major speedup).

        Args:
            frame_image: PIL Image (RGB) of a single video frame

        Returns:
            Grayscale alpha mask as PIL Image (mode 'L') at full frame resolution
        """
        # Enhancement for rembg quality (better contrast = better mask)
        frame_image = ImageEnhance.Contrast(frame_image).enhance(1.1)
        frame_image = ImageEnhance.Color(frame_image).enhance(1.15)

        if frame_image.mode != 'RGB':
            frame_image = frame_image.convert('RGB')

        frame_w, frame_h = frame_image.size

        if REMBG_AVAILABLE and self.rembg_session:
            try:
                # First frame: full-frame rembg to detect bbox
                if not self._rembg_crop_initialized:
                    no_bg = remove(frame_image, session=self.rembg_session,
                                   post_process_mask=True, alpha_matting=True)
                    no_bg = self._clean_alpha_mask(no_bg)

                    # Detect pottery bounding box with padding
                    bbox = no_bg.getbbox()
                    if bbox:
                        pad_x = int((bbox[2] - bbox[0]) * 0.15)
                        pad_y = int((bbox[3] - bbox[1]) * 0.15)
                        self._ref_crop = (
                            max(0, bbox[0] - pad_x),
                            max(0, bbox[1] - pad_y),
                            min(frame_w, bbox[2] + pad_x),
                            min(frame_h, bbox[3] + pad_y),
                        )
                    else:
                        self._ref_crop = (0, 0, frame_w, frame_h)
                    self._rembg_crop_initialized = True

                    # Extract alpha at full frame resolution for this first frame
                    return no_bg.split()[3]

                # Subsequent frames: crop to bbox before rembg (~60% fewer pixels)
                crop = self._ref_crop
                cropped = frame_image.crop(crop)
                no_bg = remove(cropped, session=self.rembg_session,
                               post_process_mask=True, alpha_matting=True)
                no_bg = self._clean_alpha_mask(no_bg)

                # Place crop-sized mask back into full-frame-sized mask
                full_mask = Image.new('L', (frame_w, frame_h), 0)
                full_mask.paste(no_bg.split()[3], (crop[0], crop[1]))
                return full_mask

            except Exception:
                return Image.new('L', (frame_w, frame_h), 255)
        else:
            return Image.new('L', (frame_w, frame_h), 255)

    def composite_frame(self, frame_image: Image.Image, alpha_mask: Image.Image,
                        frame_index: int = 0, total_frames: int = 1) -> Image.Image:
        """
        Phase 2: Composite a frame using a pre-extracted alpha mask.

        Composites directly at output resolution (VIDEO_WIDTH x VIDEO_HEIGHT).
        No fake upscale/downscale — pottery is scaled from crop to final size.
        Glow, rim light, and zoom panels applied at output resolution.
        HUD is applied separately.

        Args:
            frame_image: PIL Image (RGB) of a single video frame
            alpha_mask: Grayscale alpha mask (mode 'L') from extract_mask()
            frame_index: Current frame index (0-based) for animation
            total_frames: Total number of frames in the video

        Returns:
            Composited RGB image at VIDEO_WIDTH x VIDEO_HEIGHT (no HUD)
        """
        # Enhancement for visual output (matches the enhancement used in extract_mask)
        frame_image = ImageEnhance.Contrast(frame_image).enhance(1.1)
        frame_image = ImageEnhance.Color(frame_image).enhance(1.15)

        if frame_image.mode != 'RGB':
            frame_image = frame_image.convert('RGB')

        # Build RGBA piece from raw frame + alpha mask
        piece = frame_image.convert('RGBA')
        piece.putalpha(alpha_mask)

        # Crop using bbox from extract_mask (already set on first frame)
        piece = piece.crop(self._ref_crop)

        # Lock dimensions from first frame, scale all frames identically
        if self._ref_size is None:
            self._ref_size = piece.size

        ref_w, ref_h = self._ref_size

        # Calculate target dimensions (for VIDEO_WIDTH x VIDEO_HEIGHT canvas)
        header_h = HEADER_HEIGHT // 2
        footer_h = FOOTER_HEIGHT // 2
        max_width = int(VIDEO_WIDTH * self.zoom)
        usable_height = VIDEO_HEIGHT - header_h - footer_h
        max_height = int(usable_height * self.zoom)

        ref_ratio = ref_w / ref_h
        max_ratio = max_width / max_height

        if ref_ratio > max_ratio:
            target_w = max_width
            target_h = int(max_width / ref_ratio)
        else:
            target_h = max_height
            target_w = int(max_height * ref_ratio)

        # Scale piece from crop directly to output size (LANCZOS)
        piece_scaled = piece.resize((target_w, target_h), Image.Resampling.LANCZOS)

        # Center position
        x = (VIDEO_WIDTH - target_w) // 2
        y = header_h + (usable_height - target_h) // 2

        # Paste piece onto space background at output resolution
        canvas = self.space_bg_base.resize(
            (VIDEO_WIDTH, VIDEO_HEIGHT), Image.Resampling.LANCZOS
        ).convert('RGBA')
        canvas.paste(piece_scaled, (x, y), piece_scaled)

        # Alpha mask at output resolution for rim light and zoom scoring
        alpha = piece_scaled.split()[3]

        # Add center glow at 1x (cached after frame 0)
        if self._cached_glow is None:
            self._cached_glow = self._add_center_glow_raw(frame_image)
        canvas = Image.alpha_composite(canvas, self._cached_glow)

        # Add rim light (cached after frame 0)
        bbox = (x, y, target_w, target_h)
        if self._cached_rim is None or self._cached_rim_bbox != bbox:
            self._cached_rim = self._add_rim_light_raw(alpha, bbox)
            self._cached_rim_bbox = bbox
        canvas = Image.alpha_composite(canvas, self._cached_rim)

        # Score zoom regions on first frame, cache for reuse
        if self._zoom_regions is None:
            self._zoom_regions = self._score_zoom_regions(canvas, alpha, bbox)

        # Add zoom panels
        if self._zoom_regions:
            canvas = self._add_zoom_panels_video(canvas, bbox)

        return canvas.convert('RGB')

    def process_frame(self, frame_image: Image.Image, frame_index: int = 0,
                      total_frames: int = 1) -> Image.Image:
        """
        Process a single video frame: remove bg, composite, glow, rim light, HUD.

        Backward-compatible method that delegates to extract_mask + composite_frame + HUD.
        Both extract_mask and composite_frame enhance the raw frame identically,
        so the mask from the enhanced frame aligns with the enhanced compositing.

        Args:
            frame_image: PIL Image (RGB) of a single video frame
            frame_index: Current frame index (0-based) for animation
            total_frames: Total number of frames in the video

        Returns:
            Processed RGB image at VIDEO_WIDTH x VIDEO_HEIGHT
        """
        alpha_mask = self.extract_mask(frame_image)
        composited = self.composite_frame(frame_image, alpha_mask,
                                          frame_index, total_frames)

        # Apply HUD overlay
        if self.animate:
            hud = self._build_hud_overlay(frame_index, total_frames)
        else:
            hud = self.hud_overlay
        canvas = composited.convert('RGBA')
        canvas = Image.alpha_composite(canvas, hud)
        return canvas.convert('RGB')

    def _score_zoom_regions(self, canvas: Image.Image, alpha_mask: Image.Image,
                            bbox: Tuple[int, int, int, int]) -> list:
        """Score zoom regions on the pottery piece. Returns list of (rx1, ry1, rx2, ry2)."""
        bx, by, bw, bh = bbox

        alpha_bbox = alpha_mask.getbbox()
        if not alpha_bbox or (alpha_bbox[2] - alpha_bbox[0]) < 40 or (alpha_bbox[3] - alpha_bbox[1]) < 40:
            return []

        ax1, ay1, ax2, ay2 = alpha_bbox
        piece_w = ax2 - ax1
        piece_h = ay2 - ay1

        piece_region = alpha_mask.crop((ax1, ay1, ax2, ay2))
        piece_color = canvas.crop((bx + ax1, by + ay1, bx + ax2, by + ay2)).convert('HSV')
        piece_gray = canvas.crop((bx + ax1, by + ay1, bx + ax2, by + ay2)).convert('L')

        grid_rows, grid_cols = 4, 4
        cell_w = piece_w / grid_cols
        cell_h = piece_h / grid_rows

        raw_scores = []
        for row in range(grid_rows):
            for col in range(grid_cols):
                cx1 = int(col * cell_w)
                cy1 = int(row * cell_h)
                cx2 = int((col + 1) * cell_w)
                cy2 = int((row + 1) * cell_h)
                cx2 = min(cx2, piece_color.width)
                cy2 = min(cy2, piece_color.height)

                cell_color = piece_color.crop((cx1, cy1, cx2, cy2))
                cell_gray = piece_gray.crop((cx1, cy1, cx2, cy2))
                if cell_color.width < 3 or cell_color.height < 3:
                    raw_scores.append((row, col, 0, 0))
                    continue

                cell_alpha = piece_region.crop((cx1, cy1, cx2, cy2))
                alpha_pixels = list(cell_alpha.getdata())
                coverage = sum(1 for p in alpha_pixels if p > 128) / max(len(alpha_pixels), 1)
                if coverage < 0.6:
                    raw_scores.append((row, col, 0, 0))
                    continue

                hsv_pixels = list(cell_color.getdata())
                saturations = [s for _, s, _ in hsv_pixels]
                hues = [h for h, _, _ in hsv_pixels]
                avg_sat = sum(saturations) / len(saturations)
                if len(hues) > 1:
                    hue_mean = sum(hues) / len(hues)
                    hue_var = sum((h - hue_mean) ** 2 for h in hues) / len(hues)
                else:
                    hue_var = 0
                color_score = hue_var * 3 + avg_sat

                gray_pixels = list(cell_gray.getdata())
                w = cell_gray.width
                tex_score = 0
                for py in range(cell_gray.height):
                    for px in range(w):
                        idx = py * w + px
                        if px < w - 1:
                            tex_score += abs(gray_pixels[idx] - gray_pixels[idx + 1])
                        if py < cell_gray.height - 1:
                            tex_score += abs(gray_pixels[idx] - gray_pixels[idx + w])

                raw_scores.append((row, col, color_score, tex_score))

        max_color = max((s[2] for s in raw_scores), default=1) or 1
        max_tex = max((s[3] for s in raw_scores), default=1) or 1
        cell_scores = []
        for row, col, cs, ts in raw_scores:
            norm_color = cs / max_color
            norm_tex = ts / max_tex
            score = norm_color * 0.6 + norm_tex * 0.4
            vertical_ratio = row / max(grid_rows - 1, 1)
            if vertical_ratio > 0.7:
                score *= 0.05
            elif vertical_ratio > 0.4:
                score *= 0.5
            cell_scores.append((row, col, score))

        cell_scores.sort(key=lambda x: x[2], reverse=True)
        active = [(r, c, s) for r, c, s in cell_scores if s > 0]

        num_panels = 3
        selected = []

        def is_adjacent(row, col):
            return any(abs(row - sr) <= 1 and abs(col - sc) <= 1
                       for sr, sc in selected)

        if active:
            selected.append((active[0][0], active[0][1]))
            first_zone = active[0][1] // 2
            for row, col, score in active:
                if not is_adjacent(row, col) and col // 2 != first_zone:
                    selected.append((row, col))
                    break
            for row, col, score in active:
                if not is_adjacent(row, col):
                    selected.append((row, col))
                if len(selected) >= num_panels:
                    break

        # Fallback: fill remaining panels with best available cells (even if lower score)
        if len(selected) < num_panels:
            for row, col, score in cell_scores:
                if (row, col) not in selected:
                    selected.append((row, col))
                if len(selected) >= num_panels:
                    break
            # Last resort: pick center-ish regions if still not enough
            if len(selected) < num_panels:
                center_row = grid_rows // 2
                center_col = grid_cols // 2
                for dr in range(max(grid_rows, grid_cols)):
                    for r in range(max(0, center_row - dr), min(grid_rows, center_row + dr + 1)):
                        for c in range(max(0, center_col - dr), min(grid_cols, center_col + dr + 1)):
                            if (r, c) not in selected:
                                selected.append((r, c))
                            if len(selected) >= num_panels:
                                break
                        if len(selected) >= num_panels:
                            break
                    if len(selected) >= num_panels:
                        break

        crop_pixels = 100  # 150 / 1.5 = 1.5x zoom at 1x resolution
        regions = []
        for idx, (row, col) in enumerate(selected):
            center_x = ax1 + (col + 0.5) * cell_w
            center_y = ay1 + (row + 0.5) * cell_h
            half_size = crop_pixels // 2
            rx1 = max(0, int(center_x - half_size))
            ry1 = max(0, int(center_y - half_size))
            rx2 = min(alpha_mask.width, int(center_x + half_size))
            ry2 = min(alpha_mask.height, int(center_y + half_size))
            regions.append((rx1, ry1, rx2, ry2))

        return regions

    def _add_zoom_panels_video(self, canvas: Image.Image,
                               bbox: Tuple[int, int, int, int]) -> Image.Image:
        """Add zoom panels to video frame using cached regions."""
        if not self._zoom_regions:
            return canvas

        bx, by, bw, bh = bbox
        panel_width = 150
        panel_border = 2
        panel_gap = 18

        header_h = HEADER_HEIGHT // 2
        sidebar_x = VIDEO_WIDTH - panel_width - MARGIN
        start_y = header_h + 20

        w, h = VIDEO_WIDTH, VIDEO_HEIGHT
        overlay = Image.new('RGBA', (w, h), (0, 0, 0, 0))

        for i, (rx1, ry1, rx2, ry2) in enumerate(self._zoom_regions):
            if rx2 - rx1 < 5 or ry2 - ry1 < 5:
                continue

            # Offset piece-local coords to canvas coords
            canvas_rx1 = bx + rx1
            canvas_ry1 = by + ry1
            canvas_rx2 = bx + rx2
            canvas_ry2 = by + ry2

            crop_region = canvas.crop((canvas_rx1, canvas_ry1, canvas_rx2, canvas_ry2)).convert('RGBA')
            crop_resized = crop_region.resize((panel_width, panel_width), Image.Resampling.LANCZOS)

            py = start_y + i * (panel_width + panel_gap)

            draw = ImageDraw.Draw(overlay)
            draw.rectangle(
                [sidebar_x - panel_border, py - panel_border,
                 sidebar_x + panel_width + panel_border, py + panel_width + panel_border],
                fill=(*COLORS["cyan_dim"], 180)
            )
            overlay.paste(crop_resized, (sidebar_x, py))

            font_label = _find_font(14)
            label = f"ZOOM-{i + 1}"
            draw.text((sidebar_x + 4, py - panel_border - 20), label,
                     font=font_label, fill=(*COLORS["cyan_glow"], 200))

        return Image.alpha_composite(canvas.convert('RGBA'), overlay)

    def precompute_coaster_mask(self, frame_dir, total_frames: int, sample_count: int = 15,
                                 debug_dir: Path = None) -> None:
        """
        Pre-compute a coaster/banding-wheel mask using temporal variance.

        The coaster is stationary while the piece rotates. By comparing pixels
        across multiple frames, the coaster has near-zero temporal variance
        while the rotating piece has high variance. This is fundamentally more
        reliable than any single-frame brightness/saturation heuristic.

        Stores the result as self._coaster_mask (PIL Image mode 'L') at full
        frame resolution. Used by _clean_alpha_mask to zero out coaster pixels.

        Args:
            frame_dir: Directory containing extracted frames
            total_frames: Total number of frames in the video
            sample_count: Number of frames to sample for variance analysis
            debug_dir: Optional directory to save debug visualizations
        """
        import numpy as np
        from rembg import remove

        if not REMBG_AVAILABLE or not self.rembg_session:
            return

        # Sample frames evenly across the video
        indices = np.linspace(0, total_frames - 1, sample_count, dtype=int)

        # Run rembg on frame 0 to get the alpha mask
        frame_0_path = frame_dir / f"frame_{indices[0] + 1:06d}.png"
        if not frame_0_path.exists():
            return
        frame_0 = Image.open(frame_0_path).convert('RGB')
        no_bg_0 = remove(frame_0, session=self.rembg_session,
                         post_process_mask=True, alpha_matting=True)
        alpha_0 = np.array(no_bg_0.split()[3])

        # Solid alpha region from frame 0
        solid = alpha_0 > 128
        if np.sum(solid) < 1000:
            frame_0.close()
            no_bg_0.close()
            return

        h, w = alpha_0.shape

        # Collect raw pixel data AND alpha masks for ALL sampled frames
        # This is critical: rembg produces different alpha masks on different
        # frames (includes different amounts of coaster/grid). We need the
        # UNION of all alpha regions to ensure we mask fragments that appear
        # on any frame, not just frame 0.
        pixel_samples = []
        all_alphas = []
        for idx in indices:
            fpath = frame_dir / f"frame_{idx + 1:06d}.png"
            if not fpath.exists():
                continue
            frame_img = Image.open(fpath)
            raw = np.array(frame_img.convert('RGB'), dtype=np.float32)
            pixel_samples.append(raw)
            # Also compute alpha for this frame to get union
            no_bg = remove(frame_img.convert('RGB'), session=self.rembg_session,
                          post_process_mask=True, alpha_matting=True)
            all_alphas.append(np.array(no_bg.split()[3]) > 128)
            no_bg.close()
            frame_img.close()

        if len(pixel_samples) < 5:
            frame_0.close()
            no_bg_0.close()
            return

        # Union of all alpha masks across sampled frames
        # This ensures we catch fragments that appear on ANY frame
        union_alpha = np.any(np.stack(all_alphas, axis=0), axis=0)

        # Stack: (N, H, W, 3)
        stacked = np.stack(pixel_samples, axis=0)

        # Per-pixel variance across frames, averaged over RGB channels
        variance = np.var(stacked, axis=0)  # (H, W, 3)
        mean_var = np.mean(variance, axis=2)  # (H, W)

        # Only consider pixels within the UNION of all alphas (not just frame 0)
        variance_in_alpha = mean_var[union_alpha]
        # Use union for solid region too
        solid = union_alpha

        # Coaster pixels: bottom 70th percentile of variance within alpha
        # (stationary = low variance). Increased from 40th->55th->60th->70th to 
        # catch more coaster edges and floating fragments that rembg includes on
        # some frames. The banding wheel and grid have texture/shadow variance.
        coaster_var_threshold = np.percentile(variance_in_alpha, 70)

        # --- SIMPLE APPROACH: Mask everything below piece foot ---
        # Instead of using variance (which misses corners due to shadow variance),
        # use the p90 brightness boundary to find where the piece ends and mask
        # EVERYTHING below that line within the union alpha region.
        no_bg_0_arr = np.array(no_bg_0)
        rgb_0 = no_bg_0_arr[:, :, :3].astype(np.float32)
        p90_per_row = np.full(h, 0.0)
        has_solid = np.zeros(h, dtype=bool)
        alpha_rows_0 = np.where(solid.any(axis=1))[0]
        for y in alpha_rows_0:
            solid_mask = alpha_0[y, :] > 128
            if np.sum(solid_mask) > 10:
                p90_per_row[y] = np.percentile(rgb_0[y, solid_mask], 90)
                has_solid[y] = True

        p90_boundary = None
        solid_rows_0 = alpha_rows_0[has_solid[alpha_rows_0]]
        coaster_mask = np.zeros_like(solid)  # Start with empty mask
        
        if len(solid_rows_0) >= 20:
            solid_p90 = p90_per_row[solid_rows_0]
            mid_s = int(len(solid_rows_0) * 0.30)
            mid_e = int(len(solid_rows_0) * 0.50)
            if mid_e <= mid_s:
                mid_e = len(solid_rows_0)
                mid_s = max(0, mid_e - 20)
            body_p90 = float(np.median(solid_p90[mid_s:mid_e]))
            sample_size = max(10, int(len(solid_rows_0) * 0.20))
            bottom_p90 = float(np.median(solid_p90[-sample_size:]))
            p90_gap = body_p90 - bottom_p90

            if p90_gap >= 15:
                recovery_threshold = body_p90 * 0.85
                alpha_top = alpha_rows_0[0]
                alpha_bottom = alpha_rows_0[-1]
                p90_boundary = alpha_bottom  # default: no restriction
                for y in range(alpha_bottom, alpha_top - 1, -1):
                    if has_solid[y] and p90_per_row[y] >= recovery_threshold:
                        p90_boundary = y
                        break
                
                # Mask EVERYTHING in union_alpha below the p90 boundary
                # (with larger buffer to handle rembg frame-to-frame variations)
                alpha_height = alpha_bottom - alpha_top
                # Larger buffer (8% instead of 2%) to catch rembg inconsistencies
                buffer_rows = max(10, int(alpha_height * 0.08))
                cut_line = max(0, p90_boundary - buffer_rows)
                
                # Fill coaster_mask: everything in solid (union_alpha) below cut_line
                for y in range(cut_line, alpha_bottom + 1):
                    if y < h:
                        coaster_mask[y, :] = solid[y, :]
                
                # --- Insurance: extend mask upward to catch frame variations ---
                # Find all rows that have ANY mask and extend upward by 12%
                masked_rows = np.where(coaster_mask.any(axis=1))[0]
                if len(masked_rows) > 0:
                    topmost = masked_rows[0]
                    extend_amount = int(alpha_height * 0.12)  # 12% extension
                    new_top = max(0, topmost - extend_amount)
                    for y in range(new_top, topmost):
                        if y < h and solid[y, :].any():
                            coaster_mask[y, solid[y, :]] = True
            else:
                # No clear p90 gap - mask bottom 40% of alpha region
                cut_line = alpha_rows_0[int(len(alpha_rows_0) * 0.60)]
                for y in range(cut_line, alpha_rows_0[-1] + 1):
                    if y < h:
                        coaster_mask[y, :] = solid[y, :]
        else:
            # Not enough solid rows - mask bottom half
            if len(alpha_rows_0) > 0:
                cut_line = alpha_rows_0[len(alpha_rows_0) // 2]
                for y in range(cut_line, alpha_rows_0[-1] + 1):
                    if y < h:
                        coaster_mask[y, :] = solid[y, :]

        # Morphological cleanup: remove small isolated noise clusters
        # Keep only large connected components (coaster is one big blob)
        from scipy import ndimage
        labeled, num_features = ndimage.label(coaster_mask)
        if num_features > 0:
            # Keep components larger than 500 pixels
            component_sizes = ndimage.sum(coaster_mask, labeled, range(1, num_features + 1))
            large_components = set()
            for i, size in enumerate(component_sizes, 1):
                if size >= 500:
                    large_components.add(i)
            coaster_mask = np.isin(labeled, list(large_components))

        # Note: The p90 boundary detection above already restricts the mask to
        # below the piece foot. We don't need an additional bottom restriction
        # which could cut off part of the coaster/banding wheel.

        # Dilate to catch semi-transparent coaster edges and shadow boundaries
        # Increased from 6 to 12 iterations for better edge coverage of the blue wheel
        coaster_mask = ndimage.binary_dilation(coaster_mask, iterations=12)

        self._coaster_mask = Image.fromarray(
            (coaster_mask.astype(np.uint8) * 255), mode='L'
        )

        coaster_pixels = np.sum(coaster_mask)
        total_solid = np.sum(solid)
        coverage_pct = 100 * coaster_pixels / total_solid
        print(f"  Coaster mask: {coaster_pixels}/{total_solid} pixels "
              f"({coverage_pct:.1f}% of alpha)")

        # --- Debug visualization ---
        if debug_dir is not None:
            debug_dir = Path(debug_dir)
            debug_dir.mkdir(parents=True, exist_ok=True)

            # 1. Save variance heatmap
            var_norm = (mean_var - mean_var.min()) / (mean_var.max() - mean_var.min() + 1e-8)
            var_img = Image.fromarray((var_norm * 255).astype(np.uint8), mode='L')
            var_img.save(debug_dir / "variance_heatmap.png")

            # 2. Save coaster mask overlay on frame 0
            frame_0_rgb = np.array(frame_0)
            overlay = frame_0_rgb.copy()
            # Highlight coaster mask in red
            overlay[coaster_mask] = overlay[coaster_mask] * 0.5 + np.array([255, 0, 0]) * 0.5
            overlay_img = Image.fromarray(overlay.astype(np.uint8), mode='RGB')
            overlay_img.save(debug_dir / "coaster_mask_overlay.png")

            # 3. Save raw coaster mask
            self._coaster_mask.save(debug_dir / "coaster_mask_raw.png")

            # 4. Save p90 boundary visualization if detected
            if p90_boundary is not None:
                boundary_viz = frame_0_rgb.copy()
                # Draw boundary line
                boundary_viz[max(0, p90_boundary - 3):min(h, p90_boundary + 3), :, :] = [0, 255, 0]
                Image.fromarray(boundary_viz, mode='RGB').save(debug_dir / "p90_boundary.png")

            print(f"  Debug images saved to {debug_dir}")

        frame_0.close()
        no_bg_0.close()

    def _clean_alpha_mask(self, piece: Image.Image, force_cut_row: int = None) -> Image.Image:
        """
        Clean up the alpha mask from rembg to remove coaster/banding wheel artifacts.

        If a pre-computed coaster mask exists (from temporal variance analysis),
        it is subtracted from the alpha. This is the preferred method because it
        uses multi-frame information: the coaster is stationary (low variance)
        while the piece rotates (high variance).

        Falls back to p90 brightness heuristic when no pre-computed mask exists.
        """
        import numpy as np

        # --- Preferred path: use pre-computed temporal variance coaster mask ---
        if hasattr(self, '_coaster_mask') and self._coaster_mask is not None:
            coaster_img = self._coaster_mask
            # Coaster mask is at full frame resolution. If the input piece is
            # cropped (subsequent frames), crop the coaster mask to match.
            if coaster_img.size != piece.size:
                if hasattr(self, '_ref_crop') and self._ref_crop is not None:
                    coaster_img = coaster_img.crop(self._ref_crop)
                else:
                    coaster_img = None  # Can't align dimensions, skip

            if coaster_img is not None and coaster_img.size == piece.size:
                arr = np.array(piece)
                alpha = arr[:, :, 3].copy()
                coaster = np.array(coaster_img)
                # Only zero out alpha where the coaster mask is set AND alpha is nonzero
                alpha[coaster > 128] = 0
                arr[:, :, 3] = alpha
                return Image.fromarray(arr, mode='RGBA')

        # --- Fallback: p90 brightness heuristic (single-frame, less reliable) ---
        arr = np.array(piece)
        alpha = arr[:, :, 3].copy()
        h = alpha.shape[0]

        row_has_alpha = np.any(alpha > 30, axis=1)
        if not np.any(row_has_alpha):
            return piece

        bottom = h - 1 - np.argmax(row_has_alpha[::-1])
        top = np.argmax(row_has_alpha)

        alpha_height = bottom - top + 1
        if alpha_height < 40:
            alpha[bottom + 1:, :] = 0
            arr[:, :, 3] = alpha
            return Image.fromarray(arr, mode='RGBA')

        rgb = arr[:, :, :3].astype(np.float32)
        alpha_rows = np.where(row_has_alpha)[0]

        p90_per_row = np.full(h, 0.0)
        has_solid = np.zeros(h, dtype=bool)
        for y in alpha_rows:
            solid_mask = alpha[y, :] > 128
            n_solid = np.sum(solid_mask)
            if n_solid > 10:
                p90_per_row[y] = np.percentile(rgb[y, solid_mask], 90)
                has_solid[y] = True

        solid_rows = alpha_rows[has_solid[alpha_rows]]
        if len(solid_rows) < 20:
            alpha[bottom + 1:, :] = 0
            arr[:, :, 3] = alpha
            return Image.fromarray(arr, mode='RGBA')

        solid_p90 = p90_per_row[solid_rows]

        mid_start = int(len(solid_rows) * 0.30)
        mid_end = int(len(solid_rows) * 0.50)
        if mid_end <= mid_start:
            mid_end = len(solid_rows)
            mid_start = max(0, mid_end - 20)
        body_p90 = float(np.median(solid_p90[mid_start:mid_end]))

        sample_size = max(10, int(len(solid_rows) * 0.20))
        bottom_p90 = float(np.median(solid_p90[-sample_size:]))

        p90_gap = body_p90 - bottom_p90
        if p90_gap < 15:
            alpha[bottom + 1:, :] = 0
            arr[:, :, 3] = alpha
            return Image.fromarray(arr, mode='RGBA')

        recovery_threshold = body_p90 * 0.85
        detected_transition = bottom
        for y in range(bottom, top - 1, -1):
            if has_solid[y] and p90_per_row[y] >= recovery_threshold:
                detected_transition = y
                break

        transition_row = force_cut_row if force_cut_row is not None else detected_transition

        if not hasattr(self, '_cached_coaster_cut'):
            self._cached_coaster_cut = None
            self._cached_coaster_cut_h = None

        if self._cached_coaster_cut is None or self._cached_coaster_cut_h != h:
            self._cached_coaster_cut = transition_row
            self._cached_coaster_cut_h = h
        else:
            self._cached_coaster_cut = min(self._cached_coaster_cut, transition_row)

        soft_edge = 15
        hard_cut = max(top, self._cached_coaster_cut - soft_edge)

        for y in range(hard_cut, bottom + 1):
            factor = 1.0 if y <= self._cached_coaster_cut else 0.0
            alpha[y, :] = (alpha[y, :] * factor).astype(np.uint8)

        alpha[bottom + 1:, :] = 0
        arr[:, :, 3] = alpha
        return Image.fromarray(arr, mode='RGBA')

    def _add_center_glow(self, canvas: Image.Image, accent_color: tuple) -> Image.Image:
        """Add soft glow around center area using pre-sampled accent color."""
        glow = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        cx, cy = VIDEO_WIDTH // 2, VIDEO_HEIGHT // 2

        # Radial glow
        max_radius = min(VIDEO_WIDTH, VIDEO_HEIGHT) // 2 - 25
        for r in range(max_radius, 0, -5):
            alpha = int(15 * (1 - r / max_radius))
            draw.ellipse(
                [cx - r, cy - 30 - r, cx + r, cy - 30 + r],
                fill=(*accent_color, alpha)
            )

        glow = glow.filter(ImageFilter.GaussianBlur(radius=30))
        return Image.alpha_composite(canvas, glow)

    def _add_rim_light(self, canvas: Image.Image, alpha_mask: Image.Image,
                       bbox: Tuple[int, int, int, int]) -> Image.Image:
        """Add subtle cyan rim light along pottery edges."""
        if not REMBG_AVAILABLE or alpha_mask is None:
            return canvas

        bx, by, bw, bh = bbox

        edges = alpha_mask.filter(ImageFilter.FIND_EDGES)

        rim = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))

        # Cyan edge glow
        edge_rgba = Image.new('RGBA', edges.size, (0, 0, 0, 0))
        edge_rgba = Image.composite(
            Image.new('RGBA', edges.size, (*COLORS["cyan_glow"], 60)),
            edge_rgba,
            edges
        )

        # Shifted edge for directional feel
        shifted_edges = ImageChops.offset(edges, 2, -2)
        shifted_rgba = Image.new('RGBA', shifted_edges.size, (0, 0, 0, 0))
        shifted_rgba = Image.composite(
            Image.new('RGBA', shifted_edges.size, (*COLORS["cyan_glow"], 35)),
            shifted_rgba,
            shifted_edges
        )

        rim.paste(edge_rgba, (bx, by))
        rim.paste(shifted_rgba, (bx, by))
        rim = rim.filter(ImageFilter.GaussianBlur(radius=2))

        return Image.alpha_composite(canvas, rim)

    # =========================================================================
    # Cached overlays — generated from frame 0, reused for all frames
    # =========================================================================

    def _add_center_glow_raw(self, source: Image.Image) -> Image.Image:
        """Generate center glow overlay from source image. Cached after frame 0."""
        w, h = VIDEO_WIDTH, VIDEO_HEIGHT
        glow = Image.new('RGBA', (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(glow)

        cx, cy = w // 2, h // 2

        sample = source.resize((50, 50))
        center_color = sample.getpixel((25, 25))

        max_radius = min(w, h) // 2 - 25
        for r in range(max_radius, 0, -5):
            alpha = int(15 * (1 - r / max_radius))
            draw.ellipse(
                [cx - r, cy - 30 - r, cx + r, cy - 30 + r],
                fill=(*center_color, alpha)
            )

        glow = glow.filter(ImageFilter.GaussianBlur(radius=30))
        return glow

    def _add_rim_light_raw(self, alpha_mask: Image.Image,
                           bbox: Tuple[int, int, int, int]) -> Image.Image:
        """Generate rim light overlay. Cached after frame 0."""
        w, h = VIDEO_WIDTH, VIDEO_HEIGHT
        if not REMBG_AVAILABLE or alpha_mask is None:
            return Image.new('RGBA', (w, h), (0, 0, 0, 0))

        bx, by, bw, bh = bbox

        edges = alpha_mask.filter(ImageFilter.FIND_EDGES)

        rim = Image.new('RGBA', (w, h), (0, 0, 0, 0))

        edge_rgba = Image.new('RGBA', edges.size, (0, 0, 0, 0))
        edge_rgba = Image.composite(
            Image.new('RGBA', edges.size, (*COLORS["cyan_glow"], 60)),
            edge_rgba,
            edges
        )

        shifted_edges = ImageChops.offset(edges, 2, -2)
        shifted_rgba = Image.new('RGBA', shifted_edges.size, (0, 0, 0, 0))
        shifted_rgba = Image.composite(
            Image.new('RGBA', shifted_edges.size, (*COLORS["cyan_glow"], 35)),
            shifted_rgba,
            shifted_edges
        )

        rim.paste(edge_rgba, (bx, by))
        rim.paste(shifted_rgba, (bx, by))
        rim = rim.filter(ImageFilter.GaussianBlur(radius=2))

        return rim

    # =========================================================================
    # Split HUD — static base + per-frame animated layer
    # =========================================================================

    def _build_hud_static_base(self) -> Image.Image:
        """Pre-render all static HUD elements.

        Footer formatting parity with static frames:
          - COMPOSITION: one compound per line (split on |)
          - Lore: 3 lines instead of 2
        """
        hud = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(hud)
        te = self._text_elements

        header_h = HEADER_HEIGHT // 2
        footer_h = FOOTER_HEIGHT // 2
        footer_y = VIDEO_HEIGHT - footer_h
        border_pad = 12

        # --- Header background ---
        draw.rectangle([0, 0, VIDEO_WIDTH, header_h], fill=(0, 0, 0, 200))
        draw.line([(0, header_h), (VIDEO_WIDTH, header_h)],
                  fill=(*COLORS["white_soft"][:3], 255), width=1)

        # --- Footer background ---
        draw.rectangle([0, footer_y, VIDEO_WIDTH, VIDEO_HEIGHT], fill=(0, 0, 0, 220))
        draw.line([(0, footer_y), (VIDEO_WIDTH, footer_y)],
                  fill=(*COLORS["cyan_glow"], 200), width=2)

        # --- Card frame borders ---
        art_top = header_h + border_pad
        art_bottom = footer_y - border_pad
        art_left = border_pad
        art_right = VIDEO_WIDTH - border_pad
        draw.rectangle(
            [art_left, art_top, art_right, art_bottom],
            outline=(*COLORS["cyan_dim"], 160), width=1
        )

        # --- Lore text (static, full) — 3 lines like static frames ---
        y = footer_y + 10
        if te['lore']:
            lines = wrap_text(str(te['lore']), self.font_lore,
                              VIDEO_WIDTH - 2 * (MARGIN // 2), draw)
            for line in lines[:3]:
                draw.text((MARGIN // 2, y), line,
                          font=self.font_lore, fill=(*COLORS["white_soft"], 180))
                y += 20
        y += 4

        # Cyan divider
        draw.line([(MARGIN // 2, y), (VIDEO_WIDTH - MARGIN // 2, y)],
                  fill=(*COLORS["cyan_glow"], 120), width=1)
        y += 20

        # --- Two-column stats (static, full text) ---
        col_width = (VIDEO_WIDTH - 3 * (MARGIN // 2)) // 2
        right_x = MARGIN + col_width

        ly = y
        ry = y
        for label, value, col in te['stats']:
            if col == 'left':
                stat_x = MARGIN // 2
                cur_y = ly
                label_color = COLORS["cyan_dim"]
                val_color = COLORS["cyan_glow"]
            else:
                stat_x = right_x
                cur_y = ry
                label_color = COLORS["amber"]
                val_color = COLORS["amber"]

            draw.text((stat_x, cur_y), label, font=self.font_label, fill=label_color)
            cur_y += 15

            if label == 'COMPOSITION':
                # One compound per line (split on |) — parity with static frames
                compounds = [c.strip() for c in value.split('|')]
                for compound in compounds:
                    draw.text((stat_x, cur_y), compound, font=self.font_value, fill=val_color)
                    cur_y += 22
            else:
                lines = wrap_text(value, self.font_value, col_width - 10, draw)
                for line in lines[:1]:
                    draw.text((stat_x, cur_y), line, font=self.font_value, fill=val_color)
                    cur_y += 22

            if col == 'left':
                ly = cur_y
            else:
                ry = cur_y

        # --- Logo (full alpha) ---
        if self.logo:
            art_bottom_for_logo = footer_y - border_pad
            art_right_for_logo = VIDEO_WIDTH - border_pad
            logo_x = art_right_for_logo - self.logo.width - 5
            logo_y = art_bottom_for_logo - self.logo.height - 5
            hud.paste(self.logo, (logo_x, logo_y), self.logo)
        else:
            brand_text = "CERAFICA"
            brand_font = _find_font(19, bold=True)
            brand_x = (VIDEO_WIDTH - len(brand_text) * 12) // 2
            draw.text((brand_x, VIDEO_HEIGHT - 40),
                      f"\u25C8 {brand_text} \u25C8", font=brand_font, fill=COLORS["amber"])

        # --- Static header text ---
        draw.text((MARGIN // 2, 12), "Cerafica Exploration Log",
                  font=self.font_header, fill=COLORS["cyan_glow"])
        if te['planet_name']:
            name_w = int(self.font_header.getlength(te['planet_name']))
            draw.text((VIDEO_WIDTH - MARGIN // 2 - name_w, 12),
                      te['planet_name'], font=self.font_header, fill=COLORS["cyan_glow"])

        # --- Scan lines (static, offset=0) ---
        for sy in range(0, header_h, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))
        for sy in range(footer_y, VIDEO_HEIGHT, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))

        return hud

    def _build_hud_animated_layer(self, frame_index: int, total_frames: int) -> Image.Image:
        """Render per-frame animated elements: corner brackets (pulsing), scan line drift."""
        hud = Image.new('RGBA', (VIDEO_WIDTH, VIDEO_HEIGHT), (0, 0, 0, 0))
        draw = ImageDraw.Draw(hud)

        header_h = HEADER_HEIGHT // 2
        footer_h = FOOTER_HEIGHT // 2
        footer_y = VIDEO_HEIGHT - footer_h
        border_pad = 12

        art_top = header_h + border_pad
        art_bottom = footer_y - border_pad
        art_left = border_pad
        art_right = VIDEO_WIDTH - border_pad

        # Corner brackets (pulsing)
        bt = self._get_boot_timing(total_frames)
        corners_alpha = self._fade_alpha(frame_index, bt['corners_start'], bt['corners_fade'])

        if corners_alpha > 0:
            pulse = 0.7 + 0.3 * math.sin(frame_index * 0.08)
            cs = int(10 + 4 * (0.5 + 0.5 * math.sin(frame_index * 0.05)))
            corner_alpha = pulse * corners_alpha

            for (cx, cy, dx1, dy1, dx2, dy2) in [
                (art_left, art_top, 1, 0, 0, 1),
                (art_right, art_top, -1, 0, 0, 1),
                (art_left, art_bottom, 1, 0, 0, -1),
                (art_right, art_bottom, -1, 0, 0, -1),
            ]:
                r, g, b = COLORS["cyan_glow"]
                a = int(255 * corner_alpha)
                draw.line([(cx, cy), (cx + cs * dx1, cy)], fill=(r, g, b, a), width=2)
                draw.line([(cx, cy), (cx, cy + cs * dy1)], fill=(r, g, b, a), width=2)

        # Scan line drift
        scan_offset = frame_index % 4
        for sy in range(scan_offset, header_h, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))
        for sy in range(footer_y + scan_offset, VIDEO_HEIGHT, 4):
            draw.line([(0, sy), (VIDEO_WIDTH, sy)], fill=(0, 0, 0, 8))

        return hud

    def _build_hud_overlay_fast(self, frame_index: int, total_frames: int) -> Image.Image:
        """Build HUD using split static + animated approach."""
        if self._hud_static_layer is None:
            self._hud_static_layer = self._build_hud_static_base()

        animated = self._build_hud_animated_layer(frame_index, total_frames)
        return Image.alpha_composite(self._hud_static_layer, animated)

    # =========================================================================
    # Multiprocessing support — serialize/deserialize cached state
    # =========================================================================

    def get_init_state(self) -> Dict[str, Any]:
        """Extract all cached state for worker initialization.

        Returns a dict that can be passed to set_init_state() in a child process.
        """
        state = {}

        # Reference crop + size
        state['ref_crop'] = self._ref_crop
        state['ref_size'] = self._ref_size

        # Zoom regions
        state['zoom_regions'] = self._zoom_regions

        # Cached glow as bytes
        if self._cached_glow is not None:
            buf = io.BytesIO()
            self._cached_glow.save(buf, format='PNG')
            state['cached_glow_bytes'] = buf.getvalue()

        # Cached rim light as bytes
        if self._cached_rim is not None:
            buf = io.BytesIO()
            self._cached_rim.save(buf, format='PNG')
            state['cached_rim_bytes'] = buf.getvalue()
            state['cached_rim_bbox'] = self._cached_rim_bbox

        # Photo zoom panels as PNG bytes
        if self._photo_zoom_panels:
            panel_bytes = []
            for panel in self._photo_zoom_panels:
                buf = io.BytesIO()
                panel.save(buf, format='PNG')
                panel_bytes.append(buf.getvalue())
            state['photo_zoom_panel_bytes'] = panel_bytes
            state['photo_zoom_labels'] = self._photo_zoom_labels

        return state

    def set_init_state(self, state: Dict[str, Any]) -> None:
        """Restore cached state from the main process bootstrap."""
        self._ref_crop = state.get('ref_crop')
        self._ref_size = state.get('ref_size')
        self._zoom_regions = state.get('zoom_regions')

        if 'cached_glow_bytes' in state:
            buf = io.BytesIO(state['cached_glow_bytes'])
            self._cached_glow = Image.open(buf).convert('RGBA')

        if 'cached_rim_bytes' in state:
            buf = io.BytesIO(state['cached_rim_bytes'])
            self._cached_rim = Image.open(buf).convert('RGBA')
            self._cached_rim_bbox = state.get('cached_rim_bbox')

        if 'photo_zoom_panel_bytes' in state:
            self._photo_zoom_panels = []
            for panel_bytes in state['photo_zoom_panel_bytes']:
                buf = io.BytesIO(panel_bytes)
                self._photo_zoom_panels.append(Image.open(buf).convert('RGBA'))
            self._photo_zoom_labels = state.get('photo_zoom_labels', [])

