"""End-to-end UI smoke test (brief section 10): a logged-out browser on desktop and phone.

    backend/.venv/bin/python scripts/ui_smoke.py http://127.0.0.1:8080 [--shots DIR]

Clicks through like a judge: Load sample factory -> report -> Evidence Lens down to a photo ->
close gaps (approve the amber value) -> supplier letter in Hindi -> buyer link in a fresh
context -> EC proof -> copilot. Fails on any page error or missing element.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    shots = Path(sys.argv[sys.argv.index("--shots") + 1]) if "--shots" in sys.argv else None
    errors: list[str] = []
    t_all = time.perf_counter()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, vp in [("desktop", {"width": 1440, "height": 900}), ("phone", {"width": 360, "height": 780})]:
            ctx = browser.new_context(viewport=vp)
            page = ctx.new_page()
            page.on("pageerror", lambda e, n=name: errors.append(f"{n}: {e}"))
            page.goto(base + "/", wait_until="networkidle")
            t0 = time.perf_counter()
            page.get_by_role("button", name="Load sample factory").click()
            page.wait_for_url("**/p/demo-*/report", timeout=30_000)
            expect(page.get_by_text("Here's your proof").first).to_be_visible(timeout=15_000)
            load_s = time.perf_counter() - t0
            pid = page.url.split("/p/")[1].split("/")[0]
            print(f"[{name}] sample loaded in {load_s:.1f}s as {pid}")
            # no horizontal overflow
            sw = page.evaluate("document.documentElement.scrollWidth")
            assert sw <= vp["width"] + 1, f"{name}: horizontal overflow {sw}px"
            if name == "desktop":
                page.locator("button.clickable-num").first.click()
                dialog = page.get_by_role("dialog")
                expect(dialog.get_by_text("Everything behind this number")).to_be_visible()
                dialog.locator("ul.grid li button").first.click()
                expect(dialog.get_by_text("Reader 2 (crop only)")).to_be_visible()
                if shots:
                    page.wait_for_timeout(1800)
                    page.screenshot(path=str(shots / "smoke-lens.png"))
                page.keyboard.press("Escape")
                page.get_by_role("link", name="Close gaps").first.click()
                expect(page.get_by_text("Mass-balance check", exact=True)).to_be_visible()
                page.get_by_role("button", name="Approve 15.4").click()
                expect(page.get_by_text("Nothing left to approve.")).to_be_visible(timeout=10_000)
                print(f"[{name}] amber value approved")
                page.get_by_role("link", name="Report").first.click()
                page.get_by_role("button", name="Supplier data request letter").first.click()
                page.get_by_role("button", name="हिंदी").click()
                expect(page.get_by_text("सत्यापित").first).to_be_visible(timeout=10_000)
                page.keyboard.press("Escape")
                page.get_by_role("button", name="Create link").click()
                link = page.locator("input[readonly]").input_value()
                buyer = browser.new_context().new_page()
                buyer.goto(link, wait_until="networkidle")
                expect(buyer.get_by_text("CBAM data for your import")).to_be_visible()
                body = buyer.content()
                assert "MMBtu" not in body and "Doaba" not in body, "buyer link leaks plant-level inputs"
                print(f"[{name}] buyer link OK (logged-out): {link}")
                buyer.context.close()
                page.goto(base + "/proof", wait_until="networkidle")
                expect(page.get_by_text("All 8 cases pass")).to_be_visible(timeout=15_000)
                page.goto(base + "/copilot", wait_until="networkidle")
                page.get_by_role("button", name="Is scrap counted?").click()
                expect(page.get_by_text("Guidance 3, p. 107").first).to_be_visible(timeout=20_000)
                print(f"[{name}] proof + copilot OK")
            else:
                page.get_by_role("link", name="Close gaps").first.click()
                expect(page.get_by_role("heading", name="What's missing?")).to_be_visible()
                sw = page.evaluate("document.documentElement.scrollWidth")
                assert sw <= vp["width"] + 1, f"{name}: gaps overflow {sw}px"
                if shots:
                    page.screenshot(path=str(shots / "smoke-phone-gaps.png"))
                print(f"[{name}] gaps page fits {vp['width']}px")
            ctx.close()
        browser.close()
    if errors:
        print("PAGE ERRORS:\n" + "\n".join(errors))
        return 1
    print(f"UI smoke passed in {time.perf_counter() - t_all:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
