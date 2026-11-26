"""Draw the program icon (an open journal) as PNG and ICO. Run during the build."""

from pathlib import Path

from PIL import Image, ImageDraw


def draw(size: int = 256) -> Image.Image:
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(image)
    s = size / 256
    d.rounded_rectangle([8 * s, 8 * s, 248 * s, 248 * s], radius=40 * s, fill=(31, 58, 104, 255))
    # Two pages of an open book
    d.polygon([(40 * s, 70 * s), (126 * s, 84 * s), (126 * s, 206 * s), (40 * s, 192 * s)], fill=(255, 255, 255, 255))
    d.polygon([(130 * s, 84 * s), (216 * s, 70 * s), (216 * s, 192 * s), (130 * s, 206 * s)], fill=(240, 240, 240, 255))
    for k in range(6):
        y = 100 + k * 16
        d.line([(54 * s, (y + 2) * s), (112 * s, (y + 11) * s)], fill=(120, 130, 150, 255), width=max(1, int(5 * s)))
        d.line([(144 * s, (y + 11) * s), (202 * s, (y + 2) * s)], fill=(120, 130, 150, 255), width=max(1, int(5 * s)))
    d.ellipse([186 * s, 26 * s, 230 * s, 70 * s], fill=(221, 170, 40, 255))
    return image


def main(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    image = draw()
    image.save(folder / "icon.png")
    image.save(folder / "icon.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])


if __name__ == "__main__":
    main(Path(__file__).parent / "build")
