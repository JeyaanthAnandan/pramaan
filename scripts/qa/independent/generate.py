"""Render the new factory's documents (new layouts) and turn them into phone photos. Usage: generate.py OUTDIR"""

from __future__ import annotations

import io
import math
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter
from playwright.sync_api import sync_playwright

import factory as F

OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "out")
OUT.mkdir(exist_ok=True)
FONTS = str(Path(__file__).resolve().parents[3] / "demo" / "fonts")
import base64 as _b64
_f = lambda n: _b64.b64encode(open(f"{FONTS}/{n}", "rb").read()).decode()
CSS = f"""
@font-face {{ font-family: Hand; src: url(data:font/ttf;base64,{_f('Caveat.ttf')}); }}
@font-face {{ font-family: Hand2; src: url(data:font/ttf;base64,{_f('Kalam-Regular.ttf')}); }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; width: 1000px; background: #fff; color: #1d1d1d; font: 15px/1.35 Helvetica, Arial, 'Tamil Sangam MN', sans-serif; }}
.page {{ position: relative; width: 1000px; min-height: 1414px; padding: 46px 52px; overflow: hidden; }}
.wm {{ position: absolute; left: 120px; top: 640px; transform: rotate(-24deg); font: 700 64px Arial; color: rgba(200,40,40,.13); border: 6px solid rgba(200,40,40,.13); padding: 6px 22px; letter-spacing: 6px; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #555; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #eee; font-weight: 700; }}
.r {{ text-align: right; }}
.small {{ font-size: 12px; color: #444; }}
.foot {{ position: absolute; left: 52px; right: 52px; bottom: 28px; font-size: 11px; color: #666; }}
"""


def page(body: str, extra_css: str = "") -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><style>{CSS}{extra_css}</style></head><body><div class='page'>{body}<div class='wm'>TEST — FICTIONAL</div><div class='foot'>TEST document generated for an independent QA run of Pramaan. Not a real bill, invoice or company.</div></div></body></html>"


def n2(x) -> str:
    return f"{x:,.2f}"


def gas_html(b: dict) -> str:
    return page(f"""
<div style="display:flex;align-items:center;gap:18px;border-bottom:5px solid #e07b00;padding-bottom:14px">
  <div style="width:74px;height:74px;border-radius:50%;background:#0f6e6e;color:#fff;font:700 26px Arial;display:grid;place-items:center">KCG</div>
  <div><div style="font:700 26px Arial;color:#0f6e6e">Kongu City Gas Distribution Ltd (TEST)</div>
  <div class="small">Piped Natural Gas · Coimbatore Geographical Area · CIN U40200TN2019TEST001</div></div>
  <div style="margin-left:auto;text-align:right"><div style="font:700 18px Arial">INDUSTRIAL PNG BILL</div><div class="small">Original for recipient</div></div>
</div>
<div style="display:grid;grid-template-columns:1.2fr 1fr;gap:20px;margin-top:20px">
  <div><div class="small">BILLED TO</div><div style="font-weight:700">{F.COMPANY}</div><div>{F.ADDRESS}</div><div class="small">GSTIN {F.GSTIN} · Customer ID KCG-IND-0093</div></div>
  <table><tr><td>Bill number</td><td><b>{b['no']}</b></td></tr><tr><td>Bill date</td><td>{b['bill_date']}</td></tr>
  <tr><td>Billing period</td><td>{b['start']} to {b['end']}</td></tr><tr><td>Meter no.</td><td>KCG-M-77410 (TEST)</td></tr></table>
</div>
<h3 style="margin:28px 0 8px;color:#0f6e6e">Meter reading and gas supplied</h3>
<table style="width:70%">
<tr><td>Opening meter reading (SCM)</td><td class="r">{b['prev']:,}</td></tr>
<tr><td>Closing meter reading (SCM)</td><td class="r">{b['curr']:,}</td></tr>
<tr><th>Gas consumed (SCM)</th><th class="r">{b['scm']:,}</th></tr>
<tr><td>Gross calorific value, monthly average (kcal/SCM)</td><td class="r">{b['gcv']:,}</td></tr>
<tr><th>Energy supplied (MMBtu, on GCV)</th><th class="r">{b['mmbtu']:,.3f}</th></tr>
</table>
<p class="small">Energy (MMBtu) = SCM × GCV (kcal/SCM) × 4.1868 ÷ 1,055,056. GCV as certified by the transporter for the billing month.</p>
<h3 style="margin:22px 0 8px;color:#0f6e6e">Charges</h3>
<table><tr><th>Description</th><th class="r">Quantity</th><th class="r">Rate (₹)</th><th class="r">Amount (₹)</th></tr>
<tr><td>Natural gas charges (industrial PNG)</td><td class="r">{b['scm']:,} SCM</td><td class="r">{b['rate']} per SCM</td><td class="r">{n2(b['amount'])}</td></tr>
<tr><td>Meter rent</td><td></td><td></td><td class="r">1,500.00</td></tr>
<tr><td>VAT on natural gas @ 14.5 %</td><td></td><td></td><td class="r">{n2(b['vat'])}</td></tr>
<tr><th>Total payable</th><td></td><td></td><th class="r">{n2(b['amount'] + b['vat'] + 1500)}</th></tr></table>
<p style="margin-top:26px">Due date: 20 days from bill date. Pay by NEFT to Kongu City Gas (TEST) A/c 0000TEST.</p>
""")


def elec_html(e: dict) -> str:
    return page(f"""
<div style="background:#1a3d7c;color:#fff;padding:14px 18px;font:700 22px Arial">Tamil Nadu Power Distribution Corp. (TEST) — HT Industrial Bill</div>
<table style="margin-top:18px"><tr><td>Consumer</td><td>{F.COMPANY}</td></tr><tr><td>Bill no.</td><td>{e['no']}</td></tr>
<tr><td>Period</td><td>{e['start']} – {e['end']}</td></tr><tr><td>Tariff</td><td>HT III-A(1) industrial</td></tr></table>
<table style="margin-top:18px"><tr><th>Reading</th><th class="r">Value</th></tr>
<tr><td>Energy consumed (kWh)</td><td class="r">{e['kwh']:,}</td></tr><tr><td>Recorded maximum demand (kVA)</td><td class="r">{e['md_kva']}</td></tr>
<tr><td>Power factor</td><td class="r">0.96</td></tr></table>
<p>Energy charges ₹ 3,58,153.00 · Demand charges ₹ 1,05,560.00 · Electricity tax ₹ 21,489.00 · <b>Total ₹ 4,85,202.00</b></p>
""")


def rod_html(r: dict) -> str:
    amt = r["tonnes"] * r["rate"]
    color = "#7a1f1f" if r["rod"] == "carbon" else "#2c4a6e"
    desc = "Low-carbon steel wire rod, hot rolled, in coils" if r["rod"] == "carbon" else "Stainless steel wire rod, hot rolled, in coils, Ni ≥ 2.5 %"
    return page(f"""
<div style="display:flex;justify-content:space-between;align-items:flex-start;border:2px solid {color};padding:14px">
 <div><div style="font:700 24px Georgia;color:{color}">{r['supplier']}</div><div class="small">Rolling mill, Salem Steel Zone (TEST) · GSTIN 33AAACT0000R1Z2 (TEST)</div></div>
 <div style="text-align:right"><div style="font:700 20px Arial">TAX INVOICE</div><div>No. <b>{r['no']}</b></div><div>Date: {r['date']}</div></div>
</div>
<p><b>Buyer:</b> {F.COMPANY}, {F.ADDRESS}</p>
<table><tr><th>#</th><th>Description of goods</th><th>HSN</th><th>Grade / size</th><th class="r">Qty (MT)</th><th class="r">Rate (₹/MT)</th><th class="r">Taxable value (₹)</th></tr>
<tr><td>1</td><td>{desc}</td><td>{r['cn']}</td><td>{r['grade']}</td><td class="r">{r['tonnes']:.3f}</td><td class="r">{r['rate']:,}</td><td class="r">{n2(amt)}</td></tr></table>
<p>IGST @ 18 %: ₹ {n2(amt * __import__('decimal').Decimal('0.18'))} · <b>Invoice total ₹ {n2(amt * __import__('decimal').Decimal('1.18'))}</b></p>
<h3 style="margin:26px 0 8px">Mill test certificate (EN 10204 3.1) — Heat {r['heat']}</h3>
<table><tr><th>C %</th><th>Mn %</th><th>Si %</th><th>S %</th><th>P %</th><th>Cr %</th><th>Ni %</th><th>Cu %</th><th>Other alloying elements, total %</th></tr>
<tr><td>{r['c']}</td><td>{r['mn']}</td><td>{r['si']}</td><td>{r['s']}</td><td>{r['p']}</td><td>{r['cr']}</td><td>{r['ni']}</td><td>{r['cu']}</td><td>{r['other']}</td></tr></table>
<p class="small" style="margin-top:30px">Certified that the particulars given above are true and correct. For {r['supplier']} — Authorised signatory</p>
<div style="font:30px Hand;margin-top:6px;color:#1b3a8a">R. Senthil</div>
""")


def register_html() -> str:
    rows = ""
    for i, m in enumerate(F.MONTH_NAMES):
        rows += f"""<tr><td>{m} 2026</td><td class='h'>{F.PRODUCED['P1'][i]}</td><td class='h'>{F.PRODUCED['P2'][i]}</td><td class='h'>{F.ROD_CONSUMED['carbon'][i]}</td><td class='h'>{F.ROD_CONSUMED['stainless'][i]}</td><td class='h small2'>OK — {['KM', 'KM', 'SV', 'SV', 'KM', 'SV'][i]}</td></tr>"""
    return page(f"""
<div style="text-align:center"><div style="font:700 24px Georgia">உற்பத்திப் பதிவேடு / PRODUCTION REGISTER</div>
<div>{F.COMPANY} — Nut shop, Jan–Jun 2026</div></div>
<table style="margin-top:22px" class="reg"><tr><th>Month / மாதம்</th><th>Carbon-steel hexagon nuts produced (t)<br>கார்பன் நட் உற்பத்தி</th><th>Stainless-steel hexagon nuts produced (t)<br>ஸ்டெயின்லெஸ் நட் உற்பத்தி</th>
<th>Carbon-steel wire rod consumed (t)<br>கார்பன் ராடு செலவு</th><th>Stainless-steel wire rod consumed (t)<br>ஸ்டெயின்லெஸ் ராடு செலவு</th><th>Checked</th></tr>{rows}</table>
<h3 style="margin-top:28px">Rod stock / ராடு இருப்பு</h3>
<table class="reg" style="width:72%"><tr><th></th><th>Opening stock 01-01-2026 (t)</th><th>Closing stock 30-06-2026 (t)</th></tr>
<tr><td>Carbon-steel wire rod</td><td class='h'>{F.STOCK['carbon'][0]}</td><td class='h'>{F.STOCK['carbon'][1]}</td></tr>
<tr><td>Stainless-steel wire rod</td><td class='h'>{F.STOCK['stainless'][0]}</td><td class='h'>{F.STOCK['stainless'][1]}</td></tr></table>
<p style="margin-top:30px">Shop in-charge: <span style="font:30px Hand;color:#1b3a8a">K. Murugan</span></p>
""", ".reg td{height:54px} .reg td.h{font:34px Hand;color:#173a8e} .small2{font-size:22px!important} .page{background:repeating-linear-gradient(#fff 0 52px,#dfe7f3 52px 53px)}")


def scrap_html() -> str:
    rows = ""
    rod, idx, crossed = F.SCRAP_CORRECTION
    for i, m in enumerate(F.MONTH_NAMES):
        c = f"{F.SCRAP['carbon'][i]}"
        s = f"{F.SCRAP['stainless'][i]}"
        if rod == "stainless" and i == idx:
            s = f"<span class='strike'>{crossed}</span> {s}"
        rows += f"<tr><td>{m[:3]} 2026</td><td>{c}</td><td>{s}</td><td class='note'>{['sold to Ramesh Traders', '', 'end cuts heavy', '', '', 'sold'][i]}</td></tr>"
    return page(f"""
<div style="font:34px Hand2;color:#0b2f73;text-align:center">ஸ்க்ராப் பதிவேடு — Scrap & cut-offs log</div>
<div style="font:24px Hand;text-align:center;color:#0b2f73">Kaveri nut shop · Jan – Jun 2026 · tonnes (டன்)</div>
<table class="log" style="margin-top:26px"><tr><th>மாதம் / Month</th><th>கார்பன் ஸ்டீல் ஸ்க்ராப் (t)<br>Carbon steel scrap</th><th>ஸ்டெயின்லெஸ் ஸ்க்ராப் (t)<br>Stainless scrap</th><th>குறிப்பு / Note</th></tr>{rows}</table>
<div style="font:28px Hand;color:#0b2f73;margin-top:30px">Weighed at the scrap bay scale. — S. Vel</div>
""", """.page{background:repeating-linear-gradient(#fbfaf3 0 58px,#b9cbe6 58px 59px)} .log td,.log th{border:none;border-bottom:1px solid #9fb3d6;font:34px Hand;color:#0b2f73;height:58px}
.log th{font:600 17px 'Tamil Sangam MN',Arial;background:none;color:#333} .note{font-size:24px!important;color:#555!important}
.strike{position:relative;display:inline-block;margin-right:10px} .strike:after{content:'';position:absolute;left:-4px;right:-4px;top:58%;border-top:4px solid #0b2f73;transform:rotate(-4deg)}""")


def export_html(x: dict) -> str:
    rows, tot_net, tot_gross = "", 0, 0
    for k, (line, desc, net, gross, cartons) in enumerate(x["lines"], 1):
        rows += f"<tr><td>{k}</td><td>{desc}</td><td>{F.LINES[line]['cn']}</td><td class='r'>{cartons}</td><td class='r'>{net:,}</td><td class='r'>{gross:,}</td></tr>"
        tot_net += net
        tot_gross += gross
    return page(f"""
<div style="font:700 26px Arial;letter-spacing:2px;text-align:center;border-bottom:3px double #222;padding-bottom:10px">COMMERCIAL INVOICE</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:0;margin-top:16px">
 <div style="border:1px solid #555;padding:10px"><div class="small">Exporter / Shipper</div><b>{F.COMPANY}</b><br>{F.ADDRESS}<br>IEC 0000TEST33</div>
 <div style="border:1px solid #555;padding:10px"><div class="small">Invoice no. / date</div><b>{x['no']}</b> &nbsp; {x['date']}<br><div class="small" style="margin-top:8px">Buyer's order</div>PO LQ-26-{x['quarter'][-2:]}-118</div>
 <div style="border:1px solid #555;padding:10px"><div class="small">Consignee / Buyer</div><b>{F.BUYER}</b></div>
 <div style="border:1px solid #555;padding:10px"><div class="small">Country of origin of goods</div><b>India</b><div class="small" style="margin-top:8px">Port of loading / discharge</div>Chennai, India → Gothenburg, Sweden · Incoterms FCA Coimbatore</div>
</div>
<table style="margin-top:18px"><tr><th>#</th><th>Description of goods</th><th>HS / CN code</th><th class="r">Cartons</th><th class="r">Net weight (kg)</th><th class="r">Gross weight (kg)</th></tr>{rows}
<tr><th colspan="4">Total</th><th class="r">{tot_net:,}</th><th class="r">{tot_gross:,}</th></tr></table>
<p style="margin-top:22px">We declare that this invoice shows the actual price of the goods described and that all particulars are true and correct.</p>
<div style="font:30px Hand;color:#1b3a8a">A. Lakshmi — Export manager</div>
""")


def statement_html(s: dict) -> str:
    return page(f"""
<div style="border-left:8px solid #2c4a6e;padding-left:16px"><div style="font:700 24px Georgia;color:#2c4a6e">{s['supplier']}</div>
<div class="small">EAF melt shop & wire rod mill · Salem (TEST)</div></div>
<h2 style="margin-top:26px">Communication of embedded emissions to the operator (EU CBAM)</h2>
<p>To: {F.COMPANY} · Reference <b>{s['doc_no']}</b> · Issued 24-07-2026</p>
<table><tr><td style="width:44%">Product (CN code)</td><td>Stainless-steel wire rod, CN {s['cn']}</td></tr>
<tr><td>Reporting period covered</td><td>{s['period']}</td></tr>
<tr><td>Production route</td><td>{s['route']}</td></tr>
<tr><td><b>Specific embedded emissions (SEE), direct</b></td><td><b>{s['see']} t CO2e / t</b></td></tr>
<tr><td><b>Specific free allocation (SEFA), actual</b></td><td><b>{s['sefa']} t CO2e / t</b></td></tr>
<tr><td>Main reducing agent</td><td>{s['reducing_agent']}</td></tr>
<tr><td>Scrap used per tonne of crude steel</td><td>{s['scrap_per_t']} t/t</td></tr>
<tr><td>Share of pre-consumer scrap</td><td>{s['pre_consumer_pct']} %</td></tr></table>
<h3 style="margin-top:22px">Verification</h3>
<table><tr><td style="width:44%">Verifier</td><td>{s['verifier']}</td></tr><tr><td>Verification report number</td><td>{s['verification_ref']}</td></tr>
<tr><td>Verification opinion</td><td>{s['opinion']}</td></tr></table>
<p class="small" style="margin-top:26px">Data determined according to Implementing Regulation (EU) 2025/2547, Annex II. Indirect emissions are not part of the SEE of iron and steel goods.</p>
<div style="font:30px Hand;color:#1b3a8a;margin-top:10px">Dr. P. Anand — Head, Sustainability</div>
""")


def photo(png: bytes, seed: int) -> Image.Image:
    """Make a flat render look like a phone photo of paper on a desk."""
    rnd = random.Random(seed)
    doc = Image.open(io.BytesIO(png)).convert("RGB")
    w, h = doc.size
    W, H = int(w * 1.16), int(h * 1.12)
    bg = Image.new("RGB", (W, H), rnd.choice([(92, 70, 52), (70, 72, 78), (120, 104, 86)]))
    px = bg.load()
    for y in range(0, H, 2):  # grain
        shade = int(10 * math.sin(y / 23.0 + seed)) + rnd.randint(-6, 6)
        for x in range(0, W, 6):
            r, g, b = px[x, y]
            c = (max(0, r + shade), max(0, g + shade), max(0, b + shade))
            for dx in range(6):
                if x + dx < W:
                    px[x + dx, y] = c
                    if y + 1 < H:
                        px[x + dx, y + 1] = c
    ang = rnd.uniform(-3.0, 3.0)
    page = doc.rotate(ang, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=(0, 0, 0))
    mask = Image.new("L", doc.size, 255).rotate(ang, resample=Image.Resampling.BICUBIC, expand=True, fillcolor=0)
    shadow = Image.new("RGB", page.size, (20, 18, 16))
    ox, oy = (W - page.width) // 2, (H - page.height) // 2
    bg.paste(shadow, (ox + 14, oy + 18), mask.filter(ImageFilter.GaussianBlur(14)))
    bg.paste(page, (ox, oy), mask)
    # uneven light: brighter top-left, darker bottom-right
    light = Image.new("L", (W, H))
    d = ImageDraw.Draw(light)
    for i in range(0, max(W, H), 8):
        d.ellipse((-W * 0.3 + i * 0.2, -H * 0.3 + i * 0.2, W * 0.9 - i * 0.3, H * 0.9 - i * 0.3), fill=min(255, 150 + i // 12))
    light = light.filter(ImageFilter.GaussianBlur(80))
    dark = Image.new("RGB", (W, H), (0, 0, 0))
    bg = Image.composite(bg, Image.blend(bg, dark, 0.28), light)
    bg = bg.filter(ImageFilter.GaussianBlur(0.7))
    bg.thumbnail((1500, 1900), Image.Resampling.LANCZOS)
    return bg


DOCS: list[tuple[str, str]] = []
for b in F.gas_bills():
    DOCS.append((b["file"], gas_html(b)))
DOCS.append((F.ELECTRICITY["file"], elec_html(F.ELECTRICITY)))
for r in F.ROD_INVOICES:
    DOCS.append((r["file"], rod_html(r)))
DOCS.append(("register-2026-01-to-06", register_html()))
DOCS.append(("scrap-2026-01-to-06", scrap_html()))
for x in F.EXPORTS:
    DOCS.append((x["file"], export_html(x)))
DOCS.append((F.STATEMENT["file"], statement_html(F.STATEMENT)))

with sync_playwright() as p:
    br = p.chromium.launch()
    pg = br.new_page(viewport={"width": 1000, "height": 1414}, device_scale_factor=1.6)
    for k, (name, html) in enumerate(DOCS):
        pg.set_content(html, wait_until="load")
        pg.wait_for_timeout(250)
        png = pg.screenshot(full_page=True)
        (OUT / f"{name}.flat.png").write_bytes(png)
        photo(png, 1000 + k).save(OUT / f"{name}.jpg", quality=84)
        print(name)
    br.close()
