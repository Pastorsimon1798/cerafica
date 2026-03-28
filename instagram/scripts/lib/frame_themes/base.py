"""
Base class for frame themes.

All frame themes inherit from FrameTheme and implement the generate() method.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class FrameConfig:
    """Configuration for a frame theme."""
    # Canvas dimensions (4:5 Instagram portrait at 2x for quality)
    output_width: int = 2160
    output_height: int = 2700
    # Brand
    brand_name: str = ""
    logo_path: Optional[str] = None
    # Colors
    background_color: tuple = (10, 10, 18)
    text_color: tuple = (255, 255, 255)
    accent_color: tuple = (30, 195, 210)


class FrameTheme(ABC):
    """Base class for all frame themes.

    Subclasses must implement generate() to produce a framed product image.
    """

    def __init__(self, config: Optional[FrameConfig] = None, **kwargs):
        self.config = config or FrameConfig(**kwargs)

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable theme name."""
        ...

    @abstractmethod
    def generate(
        self,
        photo_path: str | Path,
        output_path: str | Path,
        product_name: str = "",
        product_info: Optional[dict] = None,
    ) -> Path:
        """Generate a framed image.

        Args:
            photo_path: Path to the source product photo.
            output_path: Where to save the framed result.
            product_name: Name of the product (for text overlays).
            product_info: Optional dict with additional product data.

        Returns:
            Path to the generated framed image.
        """
        ...
