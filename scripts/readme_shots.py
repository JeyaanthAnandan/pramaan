"""README screenshots and GIFs from a running Pramaan (local or the deployed URL).

    backend/.venv/bin/python scripts/readme_shots.py [BASE_URL]      # default http://127.0.0.1:8080

Writes docs/screenshots/: stills (1200 x 750 JPEG unless noted), evidence-lens.gif (640 x 400) and
money-moves.gif (the supplier's phone and the exporter's report side by side). Everything shown is
the fictional sample factory. Re-run after a deploy so the README shows what judges will see.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import Page, expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
B = (sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "http://127.0.0.1:8080").rstrip("/")
FONT = ROOT / "demo" / "fonts" / "NotoSans.ttf"
PAPER = (244, 242, 236)


def save(png: bytes, name: str, size: tuple[int, int] | None = (1200, 750)) -> None:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if size:
        im = im.resize(size, Image.Resampling.LANCZOS)
    im.save(OUT / f"{name}.jpg", quality=84, optimize=True, progressive=True)


def gif(frames: list[tuple[Image.Image, int]], name: str) -> None:
    ims = [f for f, _ in frames]
    pal = ims[0].quantize(colors=200, method=Image.Quantize.MEDIANCUT)
    q = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in ims]
    q[0].save(OUT / name, save_all=True, append_images=q[1:], duration=[d for _, d in frames], loop=0, optimize=True, disposal=1)
    print(f"{name}: {len(frames)} frames, {(OUT / name).stat().st_size // 1024} KB")


def top_of(pg: Page, sel: str, gap: int = 128) -> None:
    pg.evaluate(f"window.scrollTo(0, document.querySelector('{sel}').getBoundingClientRect().top + window.scrollY - {gap})")


def evidence_lens_and_stills(b) -> None:  # type: ignore[no-untyped-def]
    c = b.new_context(viewport={"width": 1440, "height": 900}, color_scheme="light")
    pg = c.new_page()
    frames: list[tuple[Image.Image, int]] = []

    def frame(ms: int) -> None:
        frames.append((Image.open(io.BytesIO(pg.screenshot())).convert("RGB").resize((640, 400), Image.Resampling.LANCZOS), ms))

    pg.goto(B + "/", wait_until="networkidle")
    pg.wait_for_timeout(3300)
    save(pg.screenshot(), "landing")
    pg.get_by_role("button", name="Load sample factory").click()
    pg.wait_for_url("**/report")
    for _ in range(5):
        pg.wait_for_timeout(220)
        frame(120)
    pg.wait_for_timeout(900)
    frame(1500)
    pid = pg.url.split("/p/")[1].split("/")[0]
    save(pg.screenshot(), "report")
    top_of(pg, "#lines", 150)
    pg.wait_for_timeout(1300)
    frame(900)
    pg.locator("#lines button.clickable-num").first.click()
    for _ in range(3):
        pg.wait_for_timeout(110)
        frame(90)
    pg.wait_for_timeout(500)
    frame(1300)
    save(pg.screenshot(), "lens-see")
    pg.get_by_role("dialog").locator("ul.grid li button").nth(2).click()
    for _ in range(8):
        pg.wait_for_timeout(260)
        frame(160)
    pg.wait_for_timeout(700)
    frame(1900)
    save(pg.screenshot(), "lens-source")
    pg.keyboard.press("Escape")
    pg.wait_for_timeout(400)
    pg.goto(f"{B}/p/{pid}/gaps", wait_until="networkidle")
    for _ in range(4):
        pg.wait_for_timeout(300)
        frame(220)
    pg.wait_for_timeout(600)
    frame(1400)
    save(pg.screenshot(), "two-readers")
    pg.get_by_role("button", name="Approve 15.4").click()
    for _ in range(5):
        pg.wait_for_timeout(160)
        frame(140)
    pg.wait_for_timeout(700)
    frame(900)
    pg.goto(f"{B}/p/{pid}/report", wait_until="networkidle")
    for _ in range(3):
        pg.wait_for_timeout(250)
        frame(150)
    pg.wait_for_timeout(900)
    frame(2200)
    gif(frames, "evidence-lens.gif")

    top_of(pg, "#next", 140)
    pg.wait_for_timeout(900)
    save(pg.screenshot(), "next-steps")
    top_of(pg, "#money")
    pg.wait_for_timeout(1900)
    pg.mouse.move(820, 560)
    pg.wait_for_timeout(500)
    save(pg.screenshot(), "money")
    top_of(pg, "#pulse")
    pg.wait_for_timeout(1800)
    pg.locator("#pulse").screenshot(path=str(OUT / "_pulse.png"))
    Image.open(OUT / "_pulse.png").convert("RGB").save(OUT / "plant-pulse.jpg", quality=84, optimize=True)
    (OUT / "_pulse.png").unlink()
    top_of(pg, "#levers")
    pg.wait_for_timeout(900)
    pg.get_by_role("button", name="EC Ex. 2 (EAF): 1.783").click()
    pg.wait_for_timeout(300)
    pg.get_by_role("button", name="Electric").click()
    pg.wait_for_timeout(1800)
    save(pg.screenshot(), "levers")
    pg.goto(f"{B}/p/{pid}/capture", wait_until="networkidle")
    pg.wait_for_timeout(1800)
    save(pg.screenshot(), "capture")
    pg.goto(B + "/proof", wait_until="networkidle")
    pg.wait_for_timeout(1800)
    save(pg.screenshot(), "proof")
    # try one photo: the handwritten scrap log, read and re-read; the value to check opens its crop
    pg.goto(B + "/try", wait_until="networkidle")
    pg.get_by_role("button", name="Handwritten scrap log").click()
    expect(pg.get_by_role("button", name="Try another page")).to_be_visible(timeout=90_000)
    pg.wait_for_timeout(1600)
    top_of(pg, "main section", 96)
    pg.wait_for_timeout(500)
    save(pg.screenshot(), "try-one-photo")
    # the tour, second stop
    pg.goto(B + "/", wait_until="networkidle")
    pg.get_by_role("button", name="Take the 90-second tour").click()
    tour = pg.locator('[role="dialog"][aria-labelledby="tour-title"]')
    expect(tour).to_be_visible(timeout=15_000)
    tour.get_by_role("button", name="Next").click()
    pg.wait_for_timeout(1600)
    save(pg.screenshot(), "tour")
    c.close()
    m = b.new_context(viewport={"width": 360, "height": 780}, device_scale_factor=2)
    mp = m.new_page()
    mpid = mp.request.post(B + "/api/demo/load", data={}).json()["project_id"]
    mp.goto(f"{B}/p/{mpid}/gaps", wait_until="networkidle")
    mp.wait_for_timeout(2200)
    save(mp.screenshot(), "mobile-gaps", None)
    m.close()


def money_moves(b) -> None:  # type: ignore[no-untyped-def]
    """The supplier's phone and the exporter's report side by side: the statement goes in, the money moves."""
    ex = b.new_context(viewport={"width": 1280, "height": 800}).new_page()
    sp = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True).new_page()
    pid = ex.request.post(B + "/api/demo/load", data={}).json()["project_id"]
    tok = ex.request.post(f"{B}/api/projects/{pid}/supplier-link", data={"process_id": "P2"}).json()["token"]
    ex.goto(f"{B}/p/{pid}/report", wait_until="networkidle")
    sp.goto(f"{B}/supplier/{tok}", wait_until="networkidle")
    ex.wait_for_timeout(2500)
    sp.wait_for_timeout(800)
    font = ImageFont.truetype(str(FONT), 17)
    small = ImageFont.truetype(str(FONT), 14)
    frames: list[tuple[Image.Image, int]] = []

    def frame(ms: int, caption: str) -> None:
        a = Image.open(io.BytesIO(ex.screenshot())).convert("RGB").resize((768, 480), Image.Resampling.LANCZOS)
        p = Image.open(io.BytesIO(sp.screenshot())).convert("RGB").resize((222, 480), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (768 + 222 + 48, 480 + 74), PAPER)
        canvas.paste(a, (16, 16))
        canvas.paste(p, (768 + 32, 16))
        d = ImageDraw.Draw(canvas)
        d.rectangle([15, 15, 16 + 768, 16 + 480], outline=(200, 196, 186))
        d.rectangle([768 + 31, 15, 768 + 32 + 222, 16 + 480], outline=(200, 196, 186))
        d.text((16, 480 + 26), caption, fill=(20, 33, 61), font=font)
        d.text((768 + 32, 480 + 28), "Supplier's phone", fill=(91, 100, 117), font=small)
        frames.append((canvas, ms))

    frame(1800, "The exporter's report: €409,545 a year secured, stainless bolts on the EU default")
    frame(1400, "The rod supplier opens the upload link on a phone — no account")
    sp.get_by_role("button", name="Send the sample statement").click()
    for _ in range(6):
        sp.wait_for_timeout(260)
        frame(220, "Its verified statement goes in; the same two AI readers check it")
    expect(sp.get_by_text("Thank you.")).to_be_visible(timeout=30_000)
    sp.wait_for_timeout(500)
    frame(1300, "Verified by two readers")
    for _ in range(40):  # the exporter's open report picks it up (it polls while a link is out)
        if ex.get_by_text("sent verified data").count():
            break
        ex.wait_for_timeout(250)
    for _ in range(8):
        ex.wait_for_timeout(120)
        frame(110, "... and the exporter's report moves by itself")
    ex.wait_for_timeout(1400)  # let the verdict finish counting (the +€ badge stays for 4.5 s)
    frame(3200, "€572,546 a year: stainless bolts €402 to €97 per tonne, 2 of 2 lines ready")
    gif(frames, "money-moves.gif")
    # stills for the README table
    Image.open(io.BytesIO(sp.screenshot(full_page=True))).convert("RGB").crop((0, 0, 390, 800)).save(
        OUT / "supplier-phone.jpg", quality=84, optimize=True
    )
    ex.evaluate("window.scrollTo(0, 0)")
    ex.wait_for_timeout(400)
    Image.open(io.BytesIO(ex.screenshot())).convert("RGB").crop((60, 80, 1220, 560)).save(
        OUT / "supplier-money-moves.jpg", quality=84, optimize=True
    )


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    with sync_playwright() as p:
        b = p.chromium.launch()
        if only in (None, "stills"):
            evidence_lens_and_stills(b)
        if only in (None, "money"):
            money_moves(b)
        b.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
