"""
Minimal Frame Theme

No border, no text overlay — just the product on a clean background
with a subtle brand watermark in the corner.
"""

from pathlib import Path
from typing import Optional

from .base import FrameTheme, FrameConfig

try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class MinimalFrameTheme(FrameTheme):
    """Minimal frame with subtle watermark only."""

    @property
    def name(self) -> str:
        return "Minimal"

    def generate(
        self,
        photo_path: str | Path,
        output_path: str | Path,
        product_name: str = "",
        product_info: Optional[dict] = None,
    ) -> Path:
        if not HAS_PIL:
            raise ImportError("Pillow is required for frame generation: pip install Pillow")

        photo_path = Path(photo_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cfg = self.config
        W, H = cfg.output_width, cfg.output_height

        # Create canvas
        canvas = Image.new("RGB", (W, H), cfg.background_color)

        # Load product photo
        photo = Image.open(photo_path).convert("RGBA")

        # Photo takes 90% of canvas, centered
        margin = int(W * 0.05)
        max_photo_w = W - (margin * 2)
        max_photo_h = H - (margin * 2)

        ratio = min(max_photo_w / photo.width, max_photo_h / photo.height)
        new_w = int(photo.width * ratio)
        new_h = int(photo.height * ratio)
        photo_resized = photo.resize((new_w, new_h), Image.LANCZOS)

        x = (W - new_w) // 2
        y = (H - new_h) // 2

        canvas.paste(photo_resized, (x, y), photo_resized)

        # Subtle brand watermark in bottom-right
        if cfg.brand_name:
            draw = ImageDraw.Draw(canvas)
            font_size = int(W * 0.018)
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

            # Very subtle: 30% opacity text color
            watermark_color = tuple(int(c * 0.3) for c in cfg.text_color)
            bbox = draw.textbbox((0, 0), cfg.brand_name, font=font)
            text_w = bbox[2] - bbox[0]
            draw.text(
                (W - margin - text_w, H - margin - font_size),
                cfg.brand_name,
                fill=watermark_color,
                font=font
            )

        canvas.save(str(output_path), quality=95)
        return output_path
