from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


def build_icon(source: Path, output_dir: Path) -> None:
    image = Image.open(source).convert("RGBA")
    pixels = []
    for red, green, blue, _alpha in image.get_flattened_data():
        alpha = max(0, min(255, (255 - min(red, green, blue)) * 4))
        pixels.append((red, green, blue, alpha))
    image.putdata(pixels)
    bounds = image.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("The source icon contains no visible pixels")
    content = image.crop(bounds)
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    content.thumbnail((860, 860), Image.Resampling.LANCZOS)
    offset = ((1024 - content.width) // 2, (1024 - content.height) // 2)
    canvas.alpha_composite(content, offset)

    output_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(output_dir / "app-icon.png", optimize=True)
    canvas.save(
        output_dir / "app-icon.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    build_icon(args.source, args.output_dir)


if __name__ == "__main__":
    main()
