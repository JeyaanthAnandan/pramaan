"""Generate the synthetic Shivalik Fasteners (SAMPLE) document set + ground truth.

HTML templates (Jinja2) -> Playwright PNG -> photo-like augmentation (perspective skew 2-6 deg,
table background, shadow, lighting, blur, noise, JPEG). Field bounding boxes are read from the
DOM and pushed through the same homography, so ground_truth.json has the exact region of every
value in the final phone-style photo, as ``box_2d = [ymin, xmin, ymax, xmax]`` normalised 0-1000.

The same set is the extraction eval dataset (backend/eval/run_extraction_eval.py).

Usage (from repo root):  backend/.venv/bin/python demo/generate_docs.py
"""

from __future__ import annotations

import json
import random
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import factory as F  # noqa: E402

TEMPLATES = HERE / "templates"
CACHE = HERE / ".cache"
OUT = HERE / "out"
DSF = 1.5  # device scale factor for crisp text
LONG_EDGE = 1600
HINDI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर"]
SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep"]


def inr(x: Decimal, places: int = 2) -> str:
    """Indian digit grouping: 10,10,825.20"""
    s = f"{x:.{places}f}"
    whole, _, frac = s.partition(".")
    neg = whole.startswith("-")
    whole = whole.lstrip("-")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if neg else "") + whole + (("." + frac) if frac else "")


def intl(x: Decimal, places: int = 0) -> str:
    return f"{x:,.{places}f}"


def dmy(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{d}-{m}-{y}"


def docs() -> list[dict[str, Any]]:
    rnd = random.Random(7)
    out: list[dict[str, Any]] = []
    # ---- gas invoices
    reading = Decimal(1_284_410)
    for i, month in enumerate(F.MONTHS):
        g = F.gas_month(i)
        y, m = month.split("-")
        start, end = f"01-{m}-{y}", f"{F.MONTH_DAYS[i]:02d}-{m}-{y}"
        nm = f"{int(m) % 12 + 1:02d}"
        vat = (g["amount"] * Decimal("0.143")).quantize(Decimal("0.01"))
        ctx = dict(
            supplier=F.GAS_SUPPLIER, company=F.COMPANY, idx=i, month=month,
            bill_no=f"DCG/26/{int(m):02d}/{30417 + i * 13:06d}", bill_date=f"03-{nm}-2026",
            period_start=start, period_end=end, due_date=f"18-{nm}-2026",
            prev=intl(reading), curr=intl(reading + g["scm"]),
            scm=g["scm"], scm_s=intl(g["scm"]), gcv=g["gcv"], gcv_s=intl(g["gcv"]),
            mmbtu=g["mmbtu"], mmbtu_s=f"{g['mmbtu']:,.3f}",
            rate=f"{g['rate']:.2f}", amount=inr(g["amount"]), vat=inr(vat), total=inr(g["amount"] + vat + Decimal(1500)),
        )
        reading += g["scm"]
        out.append({"doc_id": f"gas-{month}", "doc_type": "gas_invoice", "template": "gas_invoice.html.j2", "ctx": ctx,
                    "languages": ["en"], "period": [f"{y}-{m}-01", f"{y}-{m}-{F.MONTH_DAYS[i]:02d}"], "title": f"Gas invoice {F.MONTH_NAMES[i]} 2026"})
    # ---- electricity bills (recorded, excluded from SEE)
    old = Decimal(3_418_200)
    for j, e in enumerate(F.ELECTRICITY):
        y, m = e["month"].split("-")
        mi = int(m) - 1
        energy = (e["kwh"] * Decimal("7.35")).quantize(Decimal("0.01"))
        fixed = Decimal(500) * Decimal(260)
        duty = e["amount"] - energy - fixed
        ctx = dict(supplier=F.POWER_SUPPLIER, company=F.COMPANY, idx=j, month=e["month"], bill_no=f"SP/LS/{m}26/{5521 + j}",
                   bill_date=f"05-{int(m) % 12 + 1:02d}-2026", period_start=f"01-{m}-{y}", period_end=f"{F.MONTH_DAYS[mi]:02d}-{m}-{y}",
                   old_kwh=intl(old), new_kwh=intl(old + e["kwh"]), kwh=e["kwh"], kwh_s=intl(e["kwh"]), md=e["md_kva"], md_s=str(e["md_kva"]),
                   energy_amt=inr(energy), fixed_amt=inr(fixed), duty_amt=inr(duty), amount=inr(e["amount"]))
        old += e["kwh"]
        out.append({"doc_id": f"elec-{e['month']}", "doc_type": "electricity_bill", "template": "electricity_bill.html.j2", "ctx": ctx,
                    "languages": ["en", "hi"], "period": [f"{y}-{m}-01", f"{y}-{m}-{F.MONTH_DAYS[mi]:02d}"], "title": f"Electricity bill {F.MONTH_NAMES[mi]} 2026"})
    # ---- rod purchase invoices
    for k, inv in enumerate(F.ROD_INVOICES):
        p = F.PROCESSES[inv["process"]]
        sup = F.ROD_SUPPLIERS[inv["supplier"]]
        value = inv["tonnes"] * inv["rate"]
        tax = (value * Decimal("0.18")).quantize(Decimal("0.01"))
        ctx = dict(supplier=sup, company=F.COMPANY, inv=inv, idx=k, date_s=dmy(inv["date"]), grade=p["rod_grade"],
                   cn_display=p["rod_cn_display"], tonnes=inv["tonnes"], tonnes_s=f"{inv['tonnes']:.3f}", rate_s=inr(inv["rate"]),
                   value_s=inr(value), tax_s=inr(tax), total_s=inr(value + tax), comp=p["composition"],
                   product_desc="Carbon steel wire rod (SAE 1018)" if inv["process"] == "P1" else "Stainless steel wire rod (AISI 304)",
                   carbon="0.17" if inv["process"] == "P1" else "0.05", si="0.21" if inv["process"] == "P1" else "0.45",
                   heat=f"H{26}{k + 1:02d}{rnd.randint(100, 999)}", color="#7a3b12" if inv["supplier"] == "NWRM" else "#1f4e8c",
                   mono="NW" if inv["supplier"] == "NWRM" else "IS")
        out.append({"doc_id": f"rod-{inv['id'].replace('/', '-')}", "doc_type": "precursor_invoice", "template": "rod_invoice.html.j2", "ctx": ctx,
                    "languages": ["en"], "period": [inv["date"], inv["date"]], "title": f"Rod invoice {inv['id']}"})
    # ---- supplier statement (P1 rod, verified)
    st = F.SUPPLIER_STATEMENT
    ctx = dict(supplier=F.ROD_SUPPLIERS["NWRM"], company=F.COMPANY, st=st, verifier=F.VERIFIER, st_cn="7213 91 49",
               see_s=f"{st['see']:.3f}", sefa_s=f"{st['sefa']:.3f}", scrap_s=f"{st['scrap_per_t']:.2f}", pre_s=str(st["pre_consumer_pct"]))
    out.append({"doc_id": "stmt-NWRM-2026", "doc_type": "supplier_emissions_statement", "template": "supplier_statement.html.j2", "ctx": ctx,
                "languages": ["en"], "period": ["2026-01-01", "2026-09-30"], "title": "Supplier emissions statement (Northern Wire Rod Mills)"})
    # ---- production register (2 pages) and scrap log (2 pages)
    c1, c2 = F.rod_consumed("P1"), F.rod_consumed("P2")
    s1, s2 = F.scrap("P1"), F.scrap("P2")
    signs = ["RKB", "RKB", "R.K.", "RKB", "R.K.", "RKB", "RKB", "R.K.", "RKB"]
    for pg, rng in enumerate([range(0, 5), range(5, 9)]):
        rows = [dict(label=f"{F.MONTH_NAMES[i]} 2026", month=F.MONTHS[i], p1=str(F.PRODUCED["P1"][i]) + ".0", p2=str(F.PRODUCED["P2"][i]) + ".0",
                     c1=str(c1[i]), c2=str(c2[i]), sign=signs[i], rot=[round(rnd.uniform(-1.6, 1.6), 2) for _ in range(4)]) for i in rng]
        ctx = dict(company=F.COMPANY, rows=rows, page_no=pg + 1,
                   opening={k: str(v) for k, v in F.OPENING_STOCK.items()} if pg == 0 else None,
                   closing={k: str(v) for k, v in F.CLOSING_STOCK.items()} if pg == 1 else None)
        first, last = F.MONTHS[rng[0]], F.MONTHS[rng[-1]]
        out.append({"doc_id": f"register-{first}-to-{last[-2:]}", "doc_type": "production_register", "template": "production_register.html.j2", "ctx": ctx,
                    "languages": ["hi", "en"], "period": [f"{first}-01", f"{last}-{F.MONTH_DAYS[rng[-1]]:02d}"], "title": f"Production register p.{pg + 1}"})
    for pg, rng in enumerate([range(0, 5), range(5, 9)]):
        rows = []
        for i in rng:
            row = dict(hindi=HINDI_MONTHS[i], short=SHORT[i], month=F.MONTHS[i], s1=str(s1[i]), s2=str(s2[i]), sign=["ਗੁਰਮੀਤ", "G.S.", "ਗੁਰਮੀਤ"][i % 3],
                       rot=[round(rnd.uniform(-2.5, 2.5), 2) for _ in range(2)], alt2=None)
            if F.MONTHS[i] == "2026-06":
                row["alt2"] = "13.4"  # visible correction: 13.4 struck through, 15.4 written next to it
            rows.append(row)
        first, last = F.MONTHS[rng[0]], F.MONTHS[rng[-1]]
        ctx = dict(company=F.COMPANY, rows=rows, title_range=f"{SHORT[rng[0]]}–{SHORT[rng[-1]]} 2026")
        out.append({"doc_id": f"scrap-{first}-to-{last[-2:]}", "doc_type": "scrap_log", "template": "scrap_log.html.j2", "ctx": ctx,
                    "languages": ["pa", "hi", "en"], "period": [f"{first}-01", f"{last}-{F.MONTH_DAYS[rng[-1]]:02d}"], "title": f"Scrap log p.{pg + 1} (handwritten)",
                    "skew": 6.0 if pg == 1 else None})
    # ---- export invoices
    for k, exp in enumerate(F.EXPORTS):
        lines = []
        tv = Decimal(0)
        for proc, kg in exp["lines"].items():
            pp = F.PROCESSES[proc]
            price = Decimal("1.45") if proc == "P1" else Decimal("4.10")
            v = kg * price
            tv += v
            lines.append(dict(process=proc, desc=pp["name"] + (" (zinc-flake free, M8–M16)" if proc == "P1" else " (A2-70, M6–M12)"), cn_display=pp["cn_display"],
                              pkgs=int(kg / 1000), kg=kg, kg_s=intl(kg), value_s=intl(v, 2)))
        ctx = dict(company=F.COMPANY, buyer=F.BUYER, exp=exp, idx=k, date_s=dmy(exp["date"]), lines=lines,
                   total_kg_s=intl(sum(exp["lines"].values())), total_value_s=intl(tv, 2))
        out.append({"doc_id": f"export-{exp['quarter']}", "doc_type": "export_invoice", "template": "export_invoice.html.j2", "ctx": ctx,
                    "languages": ["en"], "period": [exp["date"], exp["date"]], "title": f"Export invoice {exp['id']}"})
    return out


# ------------------------------------------------------------------ rendering + augmentation


def render_all(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    env = Environment(loader=FileSystemLoader(str(TEMPLATES)), autoescape=True, undefined=StrictUndefined)
    CACHE.mkdir(exist_ok=True)
    (CACHE / "base.css").write_text((TEMPLATES / "base.css").read_text().replace("../fonts/", str(HERE / "fonts") + "/"))
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 900, "height": 1180}, device_scale_factor=DSF)
        for it in items:
            html_path = CACHE / f"{it['doc_id']}.html"
            html_path.write_text(env.get_template(it["template"]).render(**it["ctx"]))
            page.goto(html_path.as_uri())
            page.evaluate("document.fonts.ready")
            page.wait_for_timeout(150)
            fields = page.evaluate(
                """() => [...document.querySelectorAll('[data-f]')].map(el => {
                    const r = el.getBoundingClientRect();
                    return {field_key: el.dataset.f, value_text: el.dataset.text, unit: el.dataset.unit || '',
                            value_num: el.dataset.num || null, period: el.dataset.period || null, process: el.dataset.process || null,
                            item: el.dataset.item || null, alt: el.dataset.alt || null, label: el.dataset.label || null,
                            x: r.left + window.scrollX, y: r.top + window.scrollY, w: r.width, h: r.height};
                })"""
            )
            png = CACHE / f"{it['doc_id']}.png"
            page.locator(".page").screenshot(path=str(png))
            origin = page.evaluate("() => { const r = document.querySelector('.page').getBoundingClientRect(); return {x: r.left + window.scrollX, y: r.top + window.scrollY}; }")
            for fd in fields:
                fd["x"] = (fd["x"] - origin["x"]) * DSF
                fd["y"] = (fd["y"] - origin["y"]) * DSF
                fd["w"] *= DSF
                fd["h"] *= DSF
            results.append({**it, "png": png, "fields_px": fields})
        browser.close()
    return results


def _background(h: int, w: int, rng: np.random.Generator) -> np.ndarray:
    base = np.array(rng.choice([[62, 74, 92], [96, 104, 112], [70, 92, 120], [120, 126, 128]]), dtype=np.float32)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    grad = 0.85 + 0.25 * (xx / w) * (1 - yy / (2 * h))
    grain = rng.normal(0, 6, (h, w, 1)).astype(np.float32)
    streak = (np.sin(yy / rng.uniform(7, 15) + xx / 400.0) * 5)[..., None]
    img = base[None, None, :] * grad[..., None] + grain + streak
    return np.clip(img, 0, 255).astype(np.uint8)


def augment(item: dict[str, Any], seed: int) -> tuple[np.ndarray, list[dict[str, Any]]]:
    rng = np.random.default_rng(seed)
    doc = cv2.imread(str(item["png"]), cv2.IMREAD_COLOR)
    h, w = doc.shape[:2]
    pad = int(0.09 * max(h, w))
    H, W = h + 2 * pad, w + 2 * pad
    angle = item.get("skew") or float(rng.uniform(2, 6))
    angle *= 1 if rng.random() < 0.5 else -1
    src = np.float32([[pad, pad], [pad + w, pad], [pad + w, pad + h], [pad, pad + h]])
    c = np.float32([W / 2, H / 2])
    th = np.deg2rad(angle)
    rot = np.float32([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]])
    dst = (src - c) @ rot.T + c
    dst += rng.uniform(-0.012, 0.012, dst.shape).astype(np.float32) * max(h, w)  # keystone / hand tilt
    M = cv2.getPerspectiveTransform(src, dst.astype(np.float32))

    canvas = np.zeros((H, W, 3), np.uint8)
    canvas[pad : pad + h, pad : pad + w] = doc
    mask = np.zeros((H, W), np.uint8)
    mask[pad : pad + h, pad : pad + w] = 255
    warped = cv2.warpPerspective(canvas, M, (W, H), flags=cv2.INTER_CUBIC)
    wmask = cv2.warpPerspective(mask, M, (W, H), flags=cv2.INTER_LINEAR)

    bg = _background(H, W, rng)
    shadow = cv2.GaussianBlur(np.roll(np.roll(wmask, 18, 0), 14, 1), (0, 0), 22).astype(np.float32) / 255.0
    bg = (bg.astype(np.float32) * (1 - 0.55 * shadow[..., None])).astype(np.uint8)
    a = (wmask.astype(np.float32) / 255.0)[..., None]
    img = (warped.astype(np.float32) * a + bg.astype(np.float32) * (1 - a))

    # uneven lighting (phone held over a desk) + a soft hand shadow band
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    cx, cy = rng.uniform(0.2, 0.8) * W, rng.uniform(0.1, 0.5) * H
    light = 1.06 - 0.28 * (np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2) / np.hypot(W, H))
    band = 1 - 0.12 * np.exp(-(((xx * 0.6 + yy * 0.8) - rng.uniform(0.4, 1.2) * W) ** 2) / (2 * (0.08 * W) ** 2))
    img = img * (light * band)[..., None]
    img = cv2.GaussianBlur(np.clip(img, 0, 255).astype(np.uint8), (0, 0), float(rng.uniform(0.5, 0.9)))
    img = np.clip(img.astype(np.float32) + rng.normal(0, 3.2, img.shape), 0, 255).astype(np.uint8)

    scale = LONG_EDGE / max(H, W)
    img = cv2.resize(img, (int(W * scale), int(H * scale)), interpolation=cv2.INTER_AREA)
    fh, fw = img.shape[:2]

    fields = []
    for fd in item["fields_px"]:
        x0, y0 = fd["x"] + pad, fd["y"] + pad
        pts = np.float32([[[x0, y0]], [[x0 + fd["w"], y0]], [[x0 + fd["w"], y0 + fd["h"]]], [[x0, y0 + fd["h"]]]])
        t = cv2.perspectiveTransform(pts, M)[:, 0, :] * scale
        xmin, ymin = t.min(0)
        xmax, ymax = t.max(0)
        box = [int(round(ymin / fh * 1000)), int(round(xmin / fw * 1000)), int(round(ymax / fh * 1000)), int(round(xmax / fw * 1000))]
        rec = {k: fd[k] for k in ["field_key", "value_text", "unit", "value_num", "period", "process", "item", "alt", "label"] if fd.get(k) not in (None, "")}
        rec["box_2d"] = [max(0, min(1000, v)) for v in box]
        rec["page"] = 0
        fields.append(rec)
    return img, fields


def main() -> int:
    items = docs()
    rendered = render_all(items)
    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    truth = []
    for n, it in enumerate(rendered):
        img, fields = augment(it, seed=1000 + n)
        fname = f"{it['doc_id']}.jpg"
        cv2.imwrite(str(OUT / fname), img, [cv2.IMWRITE_JPEG_QUALITY, 74])
        truth.append({
            "doc_id": it["doc_id"], "file": f"out/{fname}", "doc_type": it["doc_type"], "title": it["title"],
            "languages": it["languages"], "period": it["period"], "width": int(img.shape[1]), "height": int(img.shape[0]),
            "fields": fields,
        })
        print(f"{fname:42s} {it['doc_type']:30s} fields={len(fields)}")
    meta = {
        "factory": F.COMPANY["name"],
        "note": "SAMPLE - FICTIONAL. Generated by demo/generate_docs.py; ground truth = values and regions as rendered.",
        "box_format": "[ymin, xmin, ymax, xmax] normalised 0-1000 on the final JPEG",
        "summary": {k: {kk: str(vv) for kk, vv in v.items()} if isinstance(v, dict) else str(v) for k, v in F.summary().items()},
        "documents": truth,
    }
    (HERE / "ground_truth.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")
    print(f"{len(truth)} documents, {sum(len(t['fields']) for t in truth)} fields -> demo/ground_truth.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
