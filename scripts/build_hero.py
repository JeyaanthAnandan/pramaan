"""Rebuild the landing page's hero lens assets from the sample documents (demo/out + ground truth).

    backend/.venv/bin/python scripts/build_hero.py

Writes frontend/public/hero/<doc>.jpg and .webp (879 x 1100, shown at ~460 px, so sharp on 2x screens)
and hero.json with the highlighted values and their regions (0-1000, the same boxes as the ground truth).
"""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "frontend" / "public" / "hero"
SIZE = (879, 1100)
# document -> (title, values to light up as (field_key, value as printed))
SPEC = {
    "gas-2026-03": ("Gas invoice March 2026", [("scm", "21,192"), ("gcv_kcal_per_scm", "9,555"), ("mmbtu", "803.543")]),
    "scrap-2026-06-to-09": ("Scrap log p.2 (handwritten)", [("scrap_t", "25.1"), ("scrap_t", "15.4"), ("scrap_t", "24.7")]),
    "stmt-NWRM-2026": ("Supplier emissions statement (Northern Wire Rod Mills)", [("see", "1.567"), ("sefa", "1.242")]),
}


def main() -> int:
    gt = {d["doc_id"]: d for d in json.loads((ROOT / "demo" / "ground_truth.json").read_text())["documents"]}
    OUT.mkdir(parents=True, exist_ok=True)
    hero = []
    for doc, (title, wanted) in SPEC.items():
        d = gt[doc]
        img = Image.open(ROOT / "demo" / d["file"]).convert("RGB").resize(SIZE, Image.Resampling.LANCZOS)
        img.save(OUT / f"{doc}.jpg", quality=82, optimize=True, progressive=True)
        img.save(OUT / f"{doc}.webp", quality=78, method=6)
        fields = []
        for key, text in wanted:
            f = next(x for x in d["fields"] if x["field_key"] == key and x["value_text"] == text)
            fields.append(
                {
                    "label": f.get("label") or key,
                    "text": f["value_text"],
                    "unit": f.get("unit") or "",
                    "box": f["box_2d"],
                    "alt": f.get("alt"),
                }
            )
        hero.append(
            {
                "doc": doc,
                "src": f"/hero/{doc}.jpg",
                "webp": f"/hero/{doc}.webp",
                "w": d["width"],
                "h": d["height"],
                "title": title,
                "fields": fields,
            }
        )
        print(f"{doc}: jpg {(OUT / f'{doc}.jpg').stat().st_size // 1024} KB, webp {(OUT / f'{doc}.webp').stat().st_size // 1024} KB")
    (OUT / "hero.json").write_text(json.dumps(hero, indent=1, ensure_ascii=False) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
