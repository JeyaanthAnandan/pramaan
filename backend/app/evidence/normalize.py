"""Normalise uploads to JPEG pages so cropping, the second reader and the Evidence Lens work for
every input: phone HEIC/HEIF photos are converted, PDFs are rendered page by page (each page
becomes one document, max 12 pages per file). EXIF orientation from phone cameras is applied."""

from __future__ import annotations

import io

from PIL import Image, ImageOps

MAX_PAGES = 12
MAX_EDGE = 2400


def _jpeg(img: Image.Image) -> tuple[bytes, int, int]:
    img = ImageOps.exif_transpose(img).convert("RGB")
    if max(img.size) > MAX_EDGE:
        img.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=88)
    return out.getvalue(), img.width, img.height


def to_pages(data: bytes, content_type: str) -> list[tuple[bytes, int, int]]:
    """Return one (jpeg_bytes, width, height) per page."""
    if content_type == "application/pdf":
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        pages = []
        for i in range(min(len(pdf), MAX_PAGES)):
            bitmap = pdf[i].render(scale=2.0)  # ~144 dpi: enough for printed bills
            pages.append(_jpeg(bitmap.to_pil()))
        return pages
    if content_type in {"image/heic", "image/heif"}:
        import pillow_heif

        pillow_heif.register_heif_opener()
    return [_jpeg(Image.open(io.BytesIO(data)))]
