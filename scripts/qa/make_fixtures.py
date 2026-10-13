"""Upload fixtures for api_check.py, all made from the fictional sample photos: every accepted format
(JPG, PNG, WebP, HEIC, a 3- and a 14-page PDF, CMYK, alpha, grey, a sideways phone photo with EXIF
orientation) and the ones that must be refused (corrupt, 16 MB, text, GIF, an HTML file named .png,
a 900-megapixel PNG). Usage: make_fixtures.py [OUTDIR] (default: scripts/qa/fixtures)."""

import random
import sys
from pathlib import Path

import pillow_heif
from PIL import Image

ROOT = Path(__file__).resolve().parents[2] / "demo" / "out"
F = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "fixtures"
F.mkdir(exist_ok=True)
gas = Image.open(ROOT / "gas-2026-03.jpg")
(F / "gas.jpg").write_bytes((ROOT / "gas-2026-03.jpg").read_bytes())
gas.save(F / "gas.png")
gas.save(F / "gas.webp", quality=85)
pillow_heif.register_heif_opener()
gas.save(F / "gas.heic", quality=80)
pages = [
    Image.open(ROOT / n).convert("RGB")
    for n in ("gas-2026-01.jpg", "gas-2026-02.jpg", "rod-ISR-2026-038.jpg")
]
pages[0].save(
    F / "bills-3p.pdf", save_all=True, append_images=pages[1:], resolution=100
)
many = [pages[0]] * 14
many[0].save(F / "bills-14p.pdf", save_all=True, append_images=many[1:], resolution=50)
(F / "corrupt.jpg").write_bytes(random.Random(1).randbytes(50_000))
(F / "big.jpg").write_bytes(
    b"\xff\xd8\xff\xe0" + random.Random(2).randbytes(16 * 1024 * 1024)
)
(F / "note.txt").write_text("hello")
(F / "fake.png").write_text("<html><script>alert(1)</script></html>")
Image.new("1", (30000, 30000)).save(F / "bomb.png", optimize=True)
Image.new("RGB", (60, 4000), "white").save(F / "tall.jpg")
Image.new("RGB", (1, 1), "white").save(F / "tiny.jpg")
# EXIF orientation 6 (phone held sideways)
rot = gas.rotate(90, expand=True)
exif = Image.Exif()
exif[0x0112] = 6
rot.save(F / "rotated-exif6.jpg", exif=exif.tobytes())
gas.convert("CMYK").save(F / "cmyk.jpg")
rgba = gas.convert("RGBA")
rgba.putalpha(200)
rgba.save(F / "rgba.png")
gas.convert("L").save(F / "gray.png")
Image.new("RGB", (100, 100), "red").save(F / "anim.gif")
(F / "gas-unicode.jpg").write_bytes((ROOT / "gas-2026-03.jpg").read_bytes())
for p in sorted(F.iterdir()):
    print(f"{p.name:24} {p.stat().st_size:>10,}")
