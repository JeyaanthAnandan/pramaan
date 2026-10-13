"""Black-box test of every Pramaan endpoint over HTTP (the overnight QA pass of 14 Oct 2026).

    backend/.venv/bin/python scripts/qa/make_fixtures.py          # once: upload fixtures from the sample photos
    backend/.venv/bin/python scripts/qa/api_check.py http://127.0.0.1:8080
    backend/.venv/bin/python scripts/qa/api_check.py https://<service>.run.app --live

--live: a deployed service. Skips what would call paid Gemini repeatedly or exhaust a rate limit; its
own private test projects are deleted at the end where the service has DELETE. --only=S1,S5 runs some
sections. Lines starting PASS/FAIL are checks; NOTE lines record behaviour worth reading."""

from __future__ import annotations

import csv
import io
import json
import sys
import threading
import time
import traceback
import zipfile
from pathlib import Path

import httpx

BASE = sys.argv[1].rstrip("/")
LIVE = "--live" in sys.argv
ONLY = next(
    (a.split("=", 1)[1].split(",") for a in sys.argv if a.startswith("--only=")), None
)
FIX = (
    Path(__file__).parent / "fixtures"
)  # make_fixtures.py writes them here (git-ignored)
results: list[tuple[str, str, bool, str]] = []


def check(cid: str, name: str, cond: object, detail: str = "") -> bool:
    ok = bool(cond)
    results.append((cid, name, ok, detail))
    print(
        ("PASS " if ok else "FAIL ")
        + f"{cid:8} {name}"
        + (f"  [{detail}]" if detail else ""),
        flush=True,
    )
    return ok


def note(cid: str, text: str) -> None:
    results.append((cid, text, True, "NOTE"))
    print(f"NOTE {cid:8} {text}", flush=True)


class RetryClient(httpx.Client):
    """A 500 makes the server drop the keep-alive connection; retry once on a fresh one."""

    def request(self, *a, **kw):  # type: ignore[override]
        try:
            return super().request(*a, **kw)
        except (httpx.ReadError, httpx.RemoteProtocolError):
            return super().request(*a, **kw)


def client() -> httpx.Client:
    return RetryClient(base_url=BASE, timeout=120, follow_redirects=False)


C = client()
state: dict[str, object] = {}


def section(sid: str):
    def deco(fn):
        def run():
            if ONLY and sid not in ONLY:
                return
            print(f"\n=== {sid} {fn.__doc__ or ''}", flush=True)
            try:
                fn()
            except Exception as exc:
                check(
                    sid,
                    f"section crashed: {exc.__class__.__name__}: {exc}",
                    False,
                    traceback.format_exc()[-600:],
                )

        run.sid = sid
        return run

    return deco


def is_json_404(r: httpx.Response) -> bool:
    return r.status_code == 404 and r.headers.get("content-type", "").startswith(
        "application/json"
    )


def sse_events(
    method: str, url: str, cl: httpx.Client | None = None, max_s: float = 240, **kw
) -> list[tuple[str, dict]]:
    out: list[tuple[str, dict]] = []
    cl = cl or C
    t0 = time.time()
    with cl.stream(method, url, timeout=max_s, **kw) as r:
        if r.status_code != 200:
            return [
                ("http", {"status": r.status_code, "body": r.read().decode()[:300]})
            ]
        ev = "message"
        for line in r.iter_lines():
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    data = {"raw": line[5:]}
                out.append((ev, data))
                if ev in ("end", "done", "error") or (
                    isinstance(data, dict) and data.get("stage") in ("done", "error")
                ):
                    break
                ev = "message"
            if time.time() - t0 > max_s:
                out.append(("timeout", {}))
                break
    return out


# ---------------------------------------------------------------------------------------------- S1


@section("S1")
def s1():
    """health, SPA routes, static, headers"""
    r = C.get("/api/health")
    h = r.json()
    check(
        "S1.1",
        "GET /api/health 200 + ok",
        r.status_code == 200 and h.get("status") == "ok",
        f"sha={h.get('git_sha')} store={h.get('store')} gemini={h['models'].get('gemini_configured')}",
    )
    state["health"] = h
    r = C.get("/healthz")
    note(
        "S1.2",
        f"GET /healthz -> {r.status_code} (Cloud Run reserves /healthz; /api/health is the probe)",
    )
    r = C.head("/")
    check("S1.3", "HEAD / 200", r.status_code == 200, str(r.status_code))
    r = C.get("/")
    check(
        "S1.4",
        "GET / serves the app shell",
        r.status_code == 200
        and "<title>" in r.text
        and "text/html" in r.headers.get("content-type", ""),
        r.headers.get("content-type", ""),
    )
    for path in (
        "/p/demo-nope/report",
        "/try",
        "/proof",
        "/metrics",
        "/share/nope",
        "/supplier/nope",
        "/new",
        "/p/x/verify",
        "/some/deep/unknown/page",
    ):
        r = C.get(path)
        check(
            "S1.5",
            f"SPA deep link {path} -> 200 html",
            r.status_code == 200 and "text/html" in r.headers.get("content-type", ""),
            str(r.status_code),
        )
    r = C.get("/api/does-not-exist")
    check(
        "S1.6",
        "unknown /api path -> JSON 404",
        is_json_404(r),
        f"{r.status_code} {r.headers.get('content-type')}",
    )
    r = C.get("/assets/missing-abc123.js")
    check(
        "S1.7",
        "missing hashed asset -> 404 (not the HTML shell)",
        r.status_code == 404,
        f"{r.status_code} {r.headers.get('content-type')}",
    )
    idx = C.get("/").text
    import re

    assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', idx)
    bad = [a for a in assets if C.get(a).status_code != 200]
    check(
        "S1.8",
        f"every asset the shell references loads ({len(assets)})",
        assets and not bad,
        ",".join(bad[:3]),
    )
    a = C.get(assets[0]) if assets else None
    if a is not None:
        check(
            "S1.9",
            "hashed assets are cached immutably",
            "immutable" in a.headers.get("cache-control", ""),
            a.headers.get("cache-control", ""),
        )
    hdr = C.get("/").headers
    note(
        "S1.10",
        "security headers on /: "
        + ", ".join(
            f"{k}={hdr.get(k, '-')[:40]}"
            for k in (
                "x-content-type-options",
                "x-frame-options",
                "content-security-policy",
                "referrer-policy",
                "strict-transport-security",
            )
        ),
    )
    for p in ("/og.png", "/favicon.svg", "/robots.txt"):
        r = C.get(p)
        note("S1.11", f"GET {p} -> {r.status_code} {r.headers.get('content-type', '')}")
    r = C.get("/api/docs")
    note("S1.12", f"GET /api/docs -> {r.status_code} (interactive API docs exposed)")
    r = C.get("/", headers={"accept-encoding": "gzip"})
    note("S1.13", f"index gzip: content-encoding={r.headers.get('content-encoding')}")


# ---------------------------------------------------------------------------------------------- S2


@section("S2")
def s2():
    """sample load + project, results, evidence"""
    t0 = time.time()
    r = C.post("/api/demo/load", json={})
    d = r.json()
    check(
        "S2.1",
        "POST /api/demo/load -> own copy",
        r.status_code == 200 and str(d.get("project_id", "")).startswith("demo-"),
        f"{d.get('project_id')} {d.get('source')} in {time.time() - t0:.1f}s",
    )
    check(
        "S2.2",
        "the sample is the cached live Gemini run",
        "live" in str(d.get("source")),
        str(d.get("source")),
    )
    pid = d["project_id"]
    state["demo"] = pid
    r2 = C.post("/api/demo/load", json={}).json()
    check(
        "S2.3",
        "a second load gives a different private copy",
        r2.get("project_id") != pid,
        r2.get("project_id", ""),
    )
    state["demo2"] = r2.get("project_id")
    r = C.post(
        "/api/demo/load", content=b"{nope", headers={"content-type": "application/json"}
    )
    check(
        "S2.4", "malformed JSON body -> 422", r.status_code == 422, str(r.status_code)
    )
    g = C.get(f"/api/projects/{pid}").json()
    docs = g["documents"]
    check("S2.5", "sample has 24 documents", len(docs) == 24, str(len(docs)))
    check(
        "S2.6",
        "sample has a result, not running, open (no passcode)",
        g["has_result"] and not g["running"] and not g["project"]["protected"],
        json.dumps({k: g[k] for k in ("has_result", "running")}),
    )
    check(
        "S2.7",
        "no passcode hash leaks in the project JSON",
        "access_hash" not in json.dumps(g),
        "",
    )
    check(
        "S2.8",
        "last run is the live run, status done",
        g["last_run"]
        and g["last_run"]["status"] == "done"
        and g["last_run"]["mode"] == "live",
        f"{g['last_run'] and g['last_run'].get('mode')} {g['last_run'] and g['last_run'].get('status')}",
    )
    state["processes"] = [p["id"] for p in g["project"]["processes"]]
    res = C.get(f"/api/projects/{pid}/results").json()
    state["result"] = res
    keys = ["readiness", "buyer_summary", "calc_tree", "operations"]
    check(
        "S2.9",
        "results have readiness/buyer_summary/calc_tree/operations",
        all(k in res for k in keys),
        ",".join(k for k in keys if k not in res),
    )
    ev = C.get(f"/api/projects/{pid}/evidence").json()
    st: dict[str, int] = {}
    for e in ev:
        st[e["status"]] = st.get(e["status"], 0) + 1
    state["evidence"] = ev
    check("S2.10", "evidence list loads", len(ev) > 200, f"{len(ev)} values {st}")
    boxed = sum(1 for e in ev if e.get("box_2d"))
    check(
        "S2.11", "every photo value has a region (box)", boxed >= 222, f"{boxed} boxed"
    )
    bs = res["buyer_summary"]
    note("S2.12", "buyer summary: " + json.dumps(bs)[:400])
    r = C.get(f"/api/projects/{pid}/documents/{docs[0]['id']}/image")
    check(
        "S2.13",
        "document image serves a JPEG",
        r.status_code == 200 and r.content[:3] == b"\xff\xd8\xff",
        f"{r.headers.get('content-type')} {len(r.content)}B cache={r.headers.get('cache-control')}",
    )
    r = C.get(f"/api/projects/{pid}/documents/nope/image")
    check(
        "S2.14",
        "unknown document image -> 404",
        r.status_code == 404,
        str(r.status_code),
    )
    r = C.get("/api/projects/nope-123")
    check("S2.15", "unknown project -> 404", r.status_code == 404, str(r.status_code))
    r = C.get("/api/projects/nope-123/results")
    check(
        "S2.16",
        "unknown project results -> 404",
        r.status_code == 404,
        str(r.status_code),
    )


# ---------------------------------------------------------------------------------------------- S3


@section("S3")
def s3():
    """runs + SSE (replay on the sample copy)"""
    pid = state["demo"]
    before = C.get(f"/api/projects/{pid}/results").json()
    t0 = time.time()
    r = C.post(f"/api/projects/{pid}/runs", json={"mode": "replay", "lang": "en"})
    check(
        "S3.1",
        "start a replay run",
        r.status_code == 200 and r.json().get("mode") == "replay",
        f"{r.status_code} {r.text[:120]}",
    )
    run_id = r.json().get("run_id")
    r2 = C.post(f"/api/projects/{pid}/runs", json={"mode": "replay"})
    check(
        "S3.2",
        "a second run while one runs -> 409",
        r2.status_code == 409,
        f"{r2.status_code} {r2.text[:100]}",
    )
    evs = sse_events("GET", f"/api/projects/{pid}/runs/{run_id}/events")
    [e[0] for e in evs]
    end = [e for e in evs if e[0] == "end"]
    check(
        "S3.3",
        "SSE timeline streams to an end event",
        end and end[0][1].get("status") == "done",
        f"{len(evs)} events, end={end[0][1] if end else None}, {time.time() - t0:.1f}s",
    )
    agents = sorted(
        {e[1].get("agent") for e in evs if e[0] == "timeline" and e[1].get("agent")}
    )
    note("S3.4", f"agents seen in the timeline: {agents}")
    gr = C.get(f"/api/projects/{pid}/runs/{run_id}").json()
    check(
        "S3.5",
        "GET run -> done with metrics",
        gr.get("status") == "done" and gr.get("metrics"),
        json.dumps(gr.get("metrics"))[:300],
    )
    runs = C.get(f"/api/projects/{pid}/runs").json()
    check(
        "S3.6",
        "run list includes the new run, no events payload",
        any(x["id"] == run_id for x in runs) and all("events" not in x for x in runs),
        f"{len(runs)} runs",
    )
    after = C.get(f"/api/projects/{pid}/results").json()
    b1, b2 = before["buyer_summary"], after["buyer_summary"]
    note("S3.7", f"buyer summary before/after replay rerun equal: {b1 == b2}")
    evs2 = sse_events("GET", f"/api/projects/{pid}/runs/{run_id}/events")
    check(
        "S3.8",
        "replaying a finished run's events works (reconnect)",
        any(e[0] == "end" for e in evs2),
        f"{len(evs2)} events",
    )
    r = C.get(f"/api/projects/{pid}/runs/nope")
    check("S3.9", "unknown run -> 404", r.status_code == 404, str(r.status_code))
    if not state["health"]["models"]["gemini_configured"]:
        r = C.post(f"/api/projects/{pid}/runs", json={"mode": "live"})
        check(
            "S3.10",
            "live run without Gemini -> 503",
            r.status_code == 503,
            f"{r.status_code} {r.text[:100]}",
        )
    r = C.post(f"/api/projects/{pid}/runs", json={"mode": "bogus"})
    note("S3.11", f"run mode 'bogus' -> {r.status_code} {r.text[:120]}")
    if r.status_code == 200:
        rid = r.json()["run_id"]
        evs3 = sse_events("GET", f"/api/projects/{pid}/runs/{rid}/events", max_s=60)
        note("S3.11b", f"bogus-mode run ended: {[e for e in evs3 if e[0] == 'end']}")


# ---------------------------------------------------------------------------------------------- S4


@section("S4")
def s4():
    """evidence review (approve / edit / validation)"""
    pid = state["demo2"]
    ev = C.get(f"/api/projects/{pid}/evidence").json()
    amber = [e for e in ev if e["status"] == "NEEDS_REVIEW"]
    note(
        "S4.0",
        f"{len(amber)} values need review in the sample: "
        + "; ".join(f"{e['field_key']}={e['value_text']}" for e in amber),
    )
    if amber:
        a = amber[0]
        r = C.patch(
            f"/api/projects/{pid}/evidence/{a['id']}",
            json={"action": "approve", "user": "QA tester"},
        )
        check(
            "S4.1",
            "approve an amber value",
            r.status_code == 200 and r.json()["evidence"]["status"] == "APPROVED",
            f"{r.status_code}",
        )
        check("S4.2", "approval returns the new readiness", "readiness" in r.json(), "")
        hist = r.json()["evidence"]["history"]
        check(
            "S4.3",
            "approval is in the audit history",
            hist and hist[-1]["action"] == "approve" and hist[-1]["by"] == "QA tester",
            json.dumps(hist[-1])[:200],
        )
    green = next(
        e for e in ev if e["status"] == "VERIFIED_2R" and e["field_key"] == "scrap_t"
    )
    res0 = C.get(f"/api/projects/{pid}/results").json()
    r = C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={"action": "edit", "value_text": "999", "value_num": "999", "user": "QA"},
    )
    res1 = C.get(f"/api/projects/{pid}/results").json()
    check(
        "S4.4",
        "editing a value recalculates the result",
        r.status_code == 200
        and json.dumps(res0["calc_tree"]) != json.dumps(res1["calc_tree"]),
        f"{r.status_code}",
    )
    r = C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={
            "action": "edit",
            "value_text": str(green["value_text"]),
            "value_num": str(green["value_num"]),
            "user": "QA",
        },
    )
    res2 = C.get(f"/api/projects/{pid}/results").json()
    check(
        "S4.5",
        "editing it back restores the result",
        json.dumps(res0["buyer_summary"]) == json.dumps(res2["buyer_summary"]),
        "",
    )
    for body, code, why in (
        ({"action": "edit", "value_num": "5"}, 422, "edit without value_text"),
        (
            {"action": "edit", "value_text": "x", "value_num": "abc"},
            422,
            "non-numeric value_num",
        ),
        ({"action": "delete"}, 422, "unknown action"),
        ({}, 422, "missing action"),
    ):
        r = C.patch(f"/api/projects/{pid}/evidence/{green['id']}", json=body)
        check(
            "S4.6",
            f"{why} -> {code}",
            r.status_code == code,
            f"{r.status_code} {r.text[:100]}",
        )
    r = C.patch(f"/api/projects/{pid}/evidence/nope", json={"action": "approve"})
    check("S4.7", "unknown evidence -> 404", r.status_code == 404, str(r.status_code))
    r = C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={"action": "edit", "value_text": "x", "value_num": "NaN"},
    )
    note("S4.8", f"value_num 'NaN' -> {r.status_code} {r.text[:150]}")
    if r.status_code == 200:
        rr = C.get(f"/api/projects/{pid}/results")
        note("S4.8b", f"results after NaN edit -> {rr.status_code} {rr.text[:150]}")
        C.patch(
            f"/api/projects/{pid}/evidence/{green['id']}",
            json={
                "action": "edit",
                "value_text": str(green["value_text"]),
                "value_num": str(green["value_num"]),
            },
        )
    r = C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={"action": "edit", "value_text": "x", "value_num": "-5"},
    )
    note("S4.9", f"value_num '-5' (negative scrap) -> {r.status_code}")
    rr = C.get(f"/api/projects/{pid}/results")
    note("S4.9b", f"results after negative edit -> {rr.status_code}")
    r = C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={"action": "edit", "value_text": "x", "value_num": "1e30"},
    )
    rr = C.get(f"/api/projects/{pid}/results")
    note("S4.10", f"value_num '1e30' -> {r.status_code}; results -> {rr.status_code}")
    C.patch(
        f"/api/projects/{pid}/evidence/{green['id']}",
        json={
            "action": "edit",
            "value_text": str(green["value_text"]),
            "value_num": str(green["value_num"]),
        },
    )


# ---------------------------------------------------------------------------------------------- S5


@section("S5")
def s5():
    """exports: PDF (4 languages), Excel, verifier pack"""
    pid = state["demo"]
    import pypdfium2 as pdfium

    for lang in ("en", "hi", "ta", "vi"):
        t0 = time.time()
        r = C.get(f"/api/projects/{pid}/export/pdf", params={"lang": lang})
        ok = r.status_code == 200 and r.content[:4] == b"%PDF"
        text = ""
        if ok:
            doc = pdfium.PdfDocument(r.content)
            text = "\n".join(
                doc[i].get_textpage().get_text_range() for i in range(len(doc))
            )
            pages = len(doc)
        check(
            "S5.1",
            f"PDF report ({lang})",
            ok and len(text) > 500,
            f"{r.status_code} {len(r.content) // 1024} KB, {pages if ok else 0} pages, {time.time() - t0:.1f}s, cd={r.headers.get('content-disposition')}",
        )
        if lang == "en":
            state["pdf_text"] = text
            state["result"]["buyer_summary"]
            note("S5.1b", "PDF first 300 chars: " + text[:300].replace("\n", " | "))
        if lang in ("hi", "ta"):
            nonlatin = sum(1 for ch in text if 0x900 <= ord(ch) < 0xC00)
            note(
                "S5.2",
                f"PDF ({lang}): {nonlatin} Devanagari/Tamil characters (the PDF is written in English for the EU buyer; lang is ignored)",
            )
    r = C.get(f"/api/projects/{pid}/export/pdf", params={"lang": "xx"})
    check(
        "S5.3",
        "PDF with unknown lang falls back (no 500)",
        r.status_code == 200,
        str(r.status_code),
    )
    r = C.get(f"/api/projects/{pid}/export/xlsx")
    ok = r.status_code == 200 and r.content[:2] == b"PK"
    sheets = []
    if ok:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        wb = z.read("xl/workbook.xml").decode()
        import re

        sheets = re.findall(r'<sheet name="([^"]+)"', wb)
    check(
        "S5.4",
        "Excel workbook",
        ok and sheets,
        f"{len(r.content) // 1024} KB sheets={sheets}",
    )
    try:
        import openpyxl

        wbk = openpyxl.load_workbook(io.BytesIO(r.content))
        dims = {ws.title: ws.max_row for ws in wbk.worksheets}
        check("S5.5", "Excel opens with openpyxl", True, json.dumps(dims))
    except ImportError:
        note("S5.5", "openpyxl not installed; skipped")
    r = C.get(f"/api/projects/{pid}/export/pack")
    ok = r.status_code == 200 and r.content[:2] == b"PK"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist() if ok else []
    check(
        "S5.6",
        "verifier pack zip",
        ok and len(names) > 5,
        f"{len(r.content) // 1024} KB, {len(names)} files",
    )
    note(
        "S5.7",
        "pack files: "
        + ", ".join(n for n in names if not n.startswith("documents/"))[:600]
        + f" (+{sum(1 for n in names if n.startswith('documents/'))} documents/)",
    )
    if ok:
        z = zipfile.ZipFile(io.BytesIO(r.content))
        bad = z.testzip()
        check("S5.8", "pack zip CRCs are valid", bad is None, str(bad))
        for n in names:
            if n.endswith(".csv"):
                rows = list(csv.reader(io.StringIO(z.read(n).decode("utf-8-sig"))))
                check(
                    "S5.9",
                    f"pack {n} parses as CSV",
                    len(rows) >= 1,
                    f"{len(rows)} rows, cols={len(rows[0]) if rows else 0}",
                )
            if n.endswith(".json"):
                try:
                    json.loads(z.read(n))
                    check("S5.10", f"pack {n} parses as JSON", True)
                except Exception as exc:
                    check("S5.10", f"pack {n} parses as JSON", False, str(exc))
            if n.endswith(".xml"):
                import xml.dom.minidom

                try:
                    xml.dom.minidom.parseString(z.read(n))
                    check("S5.11", f"pack {n} is well-formed XML", True)
                except Exception as exc:
                    check("S5.11", f"pack {n} is well-formed XML", False, str(exc))
    r = C.get(f"/api/projects/{pid}/export/docx")
    check(
        "S5.12", "unknown export kind -> 404", r.status_code == 404, str(r.status_code)
    )


# ---------------------------------------------------------------------------------------------- S6


@section("S6")
def s6():
    """buyer link, spot-check, what-if, explanations, monitoring plan"""
    pid = state["demo"]
    r = C.post(f"/api/projects/{pid}/share")
    d = r.json()
    check(
        "S6.1",
        "create buyer link",
        r.status_code == 200 and d.get("token") and "/share/" in d.get("url", ""),
        d.get("url", ""),
    )
    anon = client()
    s = anon.get(f"/api/share/{d['token']}")
    check(
        "S6.2",
        "buyer link opens logged out",
        s.status_code == 200 and s.json().get("summary"),
        f"{s.status_code}",
    )
    check(
        "S6.3",
        "buyer link shows the summary only (no evidence ids/photos)",
        "doc_id" not in s.text and "box_2d" not in s.text,
        f"{len(s.text)} chars",
    )
    check(
        "S6.4", "bad buyer token -> 404", anon.get("/api/share/nope").status_code == 404
    )
    sc = C.get(f"/api/projects/{pid}/spotcheck").json()
    check("S6.5", "spot-check sample of 12", len(sc["items"]) == 12, str(sc["summary"]))
    it = sc["items"][0]
    r = C.post(
        f"/api/projects/{pid}/spotcheck/{it['id']}",
        json={"match": True, "by": "QA verifier"},
    )
    check(
        "S6.6",
        "mark a spot-check value",
        r.status_code == 200 and r.json()["mark"]["by"] == "QA verifier",
        str(r.status_code),
    )
    r = C.post(f"/api/projects/{pid}/spotcheck/{it['id']}", json={"note": "x"})
    check(
        "S6.7",
        "spot-check mark without 'match' -> 422",
        r.status_code == 422,
        str(r.status_code),
    )
    r = C.post(f"/api/projects/{pid}/spotcheck/nope", json={"match": True})
    check(
        "S6.8",
        "spot-check unknown value -> 404",
        r.status_code == 404,
        str(r.status_code),
    )
    procs = state["processes"]
    for body, code, why in (
        (
            {"process_id": procs[0], "rod_see": "1.2", "rod_sefa": "0.1"},
            200,
            "rod with supplier data",
        ),
        ({"process_id": procs[0], "heating": "electric"}, 200, "electric heating"),
        (
            {"process_id": procs[0], "scrap_pct": "5", "gas_gj_per_t": "1"},
            200,
            "scrap + gas levers",
        ),
        ({"process_id": procs[0], "rod_see": "abc"}, 422, "rod_see not a number"),
        ({"process_id": procs[0], "rod_see": "-1"}, 422, "negative rod_see"),
        ({"process_id": procs[0], "rod_see": "NaN"}, 422, "rod_see NaN"),
        ({"process_id": procs[0], "rod_see": "Infinity"}, 422, "rod_see Infinity"),
        ({"process_id": procs[0], "rod_see": "51"}, 422, "rod_see above range"),
        ({"process_id": procs[0], "scrap_pct": "61"}, 422, "scrap above 60 %"),
        ({"process_id": procs[0], "heating": "coal"}, 422, "heating coal"),
        ({"process_id": "P99"}, 404, "unknown product line"),
    ):
        r = C.post(f"/api/projects/{pid}/whatif", json=body)
        check(
            "S6.9",
            f"what-if: {why} -> {code}",
            r.status_code == code,
            f"{r.status_code} {r.text[:100] if r.status_code != code else ''}",
        )
    for lang in ("en", "hi", "ta", "vi", "xx"):
        r = C.get(f"/api/projects/{pid}/explanations", params={"lang": lang})
        check(
            "S6.10",
            f"explanations ({lang})",
            r.status_code == 200 and r.json().get("sections"),
            f"{r.status_code} {len(r.json().get('sections', [])) if r.status_code == 200 else r.text[:100]} sections",
        )
        r = C.get(f"/api/projects/{pid}/monitoring-plan", params={"lang": lang})
        check(
            "S6.11",
            f"monitoring plan ({lang})",
            r.status_code == 200,
            f"{r.status_code} {r.text[:80] if r.status_code != 200 else ''}",
        )
    for body, code, why in (
        ({"fx_inr_per_eur": "95.5"}, 200, "set FX"),
        ({"fx_inr_per_eur": "abc"}, 422, "FX not a number"),
        ({"fx_inr_per_eur": "0"}, 422, "FX zero"),
        ({"fx_inr_per_eur": "NaN"}, 422, "FX NaN"),
        ({"fx_inr_per_eur": "Infinity"}, 422, "FX Infinity"),
        ({"fx_inr_per_eur": ""}, 200, "FX cleared"),
        ({"projection_price_eur": "80"}, 200, "projection price"),
        ({"projection_price_eur": ""}, 200, "projection price cleared"),
        ({"supplier_status": {procs[0]: "requested"}}, 200, "supplier status"),
        ({"supplier_status": {procs[0]: "lost"}}, 422, "bad supplier status"),
        ({"name": "Renamed"}, 200, "rename the sample (ignored)"),
    ):
        r = C.patch(f"/api/projects/{pid}", json=body)
        check(
            "S6.12",
            f"patch project: {why} -> {code}",
            r.status_code == code,
            f"{r.status_code} {r.text[:120] if r.status_code != code else ''}",
        )
    p = C.get(f"/api/projects/{pid}").json()["project"]
    check(
        "S6.13",
        "the sample's name cannot be changed",
        p["name"] != "Renamed",
        p["name"],
    )


# ---------------------------------------------------------------------------------------------- S7


@section("S7")
def s7():
    """supplier upload link + letter"""
    pid = state["demo"]
    procs = state["processes"]
    r = C.post(f"/api/projects/{pid}/supplier-link", json={"process_id": procs[0]})
    d = r.json()
    check(
        "S7.1",
        "create supplier link",
        r.status_code == 200 and d.get("token"),
        d.get("url", ""),
    )
    tok = d["token"]
    r = C.post(f"/api/projects/{pid}/supplier-link", json={"process_id": procs[0]})
    check(
        "S7.2", "the same product line keeps its link", r.json().get("token") == tok, ""
    )
    r = C.post(f"/api/projects/{pid}/supplier-link", json={"process_id": "P99"})
    check(
        "S7.3",
        "supplier link for unknown line -> 404",
        r.status_code == 404,
        str(r.status_code),
    )
    anon = client()
    v = anon.get(f"/api/supplier/{tok}")
    check(
        "S7.4",
        "supplier opens the link without an account",
        v.status_code == 200,
        v.text[:200],
    )
    view = v.json()
    note("S7.5", "supplier view keys: " + ",".join(view.keys()))
    check(
        "S7.6",
        "supplier view does not expose other evidence/results",
        "calc_tree" not in v.text and "buyer_summary" not in v.text,
        "",
    )
    check(
        "S7.7",
        "bad supplier token -> 404",
        anon.get("/api/supplier/nope").status_code == 404,
    )
    for lang in ("en", "hi", "ta", "vi"):
        r = C.post(
            f"/api/projects/{pid}/supplier-letter",
            json={"process_id": procs[0], "lang": lang},
        )
        ok = r.status_code == 200
        check(
            "S7.8",
            f"supplier letter ({lang})",
            ok and tok in json.dumps(r.json()),
            f"{r.status_code} keys={list(r.json().keys()) if ok else r.text[:100]}",
        )
    r = C.post(f"/api/projects/{pid}/supplier-letter", json={"process_id": "P99"})
    check(
        "S7.9",
        "letter for unknown line -> 404",
        r.status_code == 404,
        str(r.status_code),
    )
    if not LIVE:
        r = anon.post(
            f"/api/supplier/{tok}/documents",
            files=[
                (
                    "files",
                    ("statement.jpg", (FIX / "gas.jpg").read_bytes(), "image/jpeg"),
                )
            ],
        )
        check(
            "S7.10",
            "supplier uploads a photo through the link",
            r.status_code == 200,
            f"{r.status_code} {r.text[:200]}",
        )
        time.sleep(3)
        v2 = anon.get(f"/api/supplier/{tok}").json()
        note("S7.11", "supplier view after upload: " + json.dumps(v2)[:400])
        owner_docs = C.get(f"/api/projects/{pid}").json()["documents"]
        mine = [
            x
            for x in owner_docs
            if str(x.get("uploaded_by", "")).startswith("supplier:")
        ]
        check(
            "S7.12",
            "the owner sees the supplier's upload",
            mine,
            f"{len(mine)} supplier docs",
        )
        if mine:
            r = anon.get(f"/api/supplier/{tok}/documents/{mine[0]['id']}/image")
            check(
                "S7.13",
                "supplier can see own upload image",
                r.status_code == 200,
                str(r.status_code),
            )
        other = C.get(f"/api/projects/{pid}").json()["documents"][0]
        r = anon.get(f"/api/supplier/{tok}/documents/{other['id']}/image")
        check(
            "S7.14",
            "supplier cannot fetch the owner's other photos",
            r.status_code == 404,
            f"{r.status_code} for {other['filename']}",
        )
        r = anon.post(f"/api/supplier/{tok}/sample")
        note(
            "S7.15",
            f"supplier 'send sample statement' -> {r.status_code} {r.text[:200]}",
        )
        r = anon.post(
            f"/api/supplier/{tok}/documents",
            files=[("files", ("x.txt", b"hello", "text/plain"))],
        )
        check(
            "S7.16",
            "supplier upload of a text file -> 415",
            r.status_code == 415,
            str(r.status_code),
        )


# ---------------------------------------------------------------------------------------------- S8


@section("S8")
def s8():
    """own private project: create, access control, uploads, product lines, delete"""
    owner = client()
    r = owner.post(
        "/api/projects",
        json={
            "name": "QA test (SAMPLE)",
            "company": "QA Fasteners (SAMPLE)",
            "city": "Ludhiana",
        },
    )
    d = r.json()
    check(
        "S8.1",
        "create a private project",
        r.status_code == 200 and d.get("protected") and d.get("access_key"),
        f"{d.get('id')} key={d.get('access_key')}",
    )
    pid, key = d["id"], d["access_key"]
    state["own"] = (pid, key)
    sc = r.headers.get("set-cookie", "")
    check(
        "S8.2",
        "owner cookie is HttpOnly, SameSite=Lax, scoped to the project",
        "HttpOnly" in sc
        and "samesite=lax" in sc.lower()
        and f"Path=/api/projects/{pid}" in sc,
        sc[:200],
    )
    if BASE.startswith("https"):
        check("S8.2b", "owner cookie is Secure on https", "Secure" in sc, "")
    r = owner.post(
        "/api/projects", json={"name": "x", "company": "y", "country": "Atlantis"}
    )
    check("S8.3", "unknown country -> 422", r.status_code == 422, str(r.status_code))
    r = owner.post("/api/projects", json={"name": "x" * 5000, "company": "y"})
    check(
        "S8.4",
        "very long name is cut to 120 chars",
        r.status_code == 200 and len(r.json()["name"]) == 120,
        str(r.status_code),
    )
    if r.status_code == 200:
        owner.delete(f"/api/projects/{r.json()['id']}")
    r = owner.post("/api/projects", json={"name": "x"})
    check("S8.5", "missing company -> 422", r.status_code == 422, str(r.status_code))
    anon = client()
    routes = [
        ("GET", f"/api/projects/{pid}", None),
        ("GET", f"/api/projects/{pid}/evidence", None),
        ("GET", f"/api/projects/{pid}/results", None),
        ("GET", f"/api/projects/{pid}/runs", None),
        ("GET", f"/api/projects/{pid}/spotcheck", None),
        ("GET", f"/api/projects/{pid}/export/pdf", None),
        ("GET", f"/api/projects/{pid}/export/pack", None),
        ("GET", f"/api/projects/{pid}/explanations", None),
        ("GET", f"/api/projects/{pid}/monitoring-plan", None),
        ("POST", f"/api/projects/{pid}/runs", {"mode": "replay"}),
        ("POST", f"/api/projects/{pid}/share", None),
        ("POST", f"/api/projects/{pid}/ask", {"question": "hi"}),
        ("POST", f"/api/projects/{pid}/whatif", {"process_id": "P1"}),
        ("POST", f"/api/projects/{pid}/supplier-link", {"process_id": "P1"}),
        ("POST", f"/api/projects/{pid}/spotcheck/x", {"match": True}),
        ("PATCH", f"/api/projects/{pid}", {"name": "pwned"}),
        ("PATCH", f"/api/projects/{pid}/evidence/x", {"action": "approve"}),
        ("PUT", f"/api/projects/{pid}/product-lines", {"lines": []}),
        ("POST", f"/api/projects/{pid}/product-lines/suggest", None),
        ("DELETE", f"/api/projects/{pid}", None),
    ]
    leaks = []
    for m, u, body in routes:
        rr = anon.request(m, u, json=body)
        if rr.status_code != 401:
            leaks.append(f"{m} {u.split(pid)[1] or '/'}={rr.status_code}")
    check(
        "S8.6",
        f"a stranger gets 401 on all {len(routes)} project routes",
        not leaks,
        ", ".join(leaks),
    )
    rr = anon.post(
        f"/api/projects/{pid}/documents",
        files=[("files", ("a.jpg", (FIX / "gas.jpg").read_bytes(), "image/jpeg"))],
    )
    check(
        "S8.7",
        "a stranger cannot upload into a private project",
        rr.status_code == 401,
        str(rr.status_code),
    )
    rr = anon.get(f"/api/projects/{pid}", headers={"X-Pramaan-Key": key})
    check(
        "S8.8",
        "X-Pramaan-Key header opens it",
        rr.status_code == 200,
        str(rr.status_code),
    )
    rr = anon.get(
        f"/api/projects/{pid}", headers={"X-Pramaan-Key": key.lower().replace("-", " ")}
    )
    check(
        "S8.9",
        "the passcode is case/separator-insensitive",
        rr.status_code == 200,
        str(rr.status_code),
    )
    rr = anon.post(f"/api/projects/{pid}/unlock", json={"passcode": "AAAA-BBBB-CCCC"})
    check("S8.10", "wrong passcode -> 401", rr.status_code == 401, str(rr.status_code))
    rr = anon.post(f"/api/projects/{pid}/unlock", json={"passcode": key})
    check(
        "S8.11",
        "right passcode unlocks and sets the cookie",
        rr.status_code == 200 and anon.get(f"/api/projects/{pid}").status_code == 200,
        str(rr.status_code),
    )
    rr = client().post("/api/projects/nope-x/unlock", json={"passcode": "x"})
    check(
        "S8.12",
        "unlock unknown project -> 404",
        rr.status_code == 404,
        str(rr.status_code),
    )
    r = owner.get(f"/api/projects/{pid}/results")
    check(
        "S8.13",
        "a new project has no results yet -> 404 with a message",
        r.status_code == 404 and "run" in r.text,
        r.text[:100],
    )
    # uploads
    expect = {
        "gas.jpg": ("image/jpeg", 200),
        "gas.png": ("image/png", 200),
        "gas.webp": ("image/webp", 200),
        "gas.heic": ("image/heic", 200),
        "bills-3p.pdf": ("application/pdf", 200),
        "rotated-exif6.jpg": ("image/jpeg", 200),
        "cmyk.jpg": ("image/jpeg", 200),
        "rgba.png": ("image/png", 200),
        "gray.png": ("image/png", 200),
        "tall.jpg": ("image/jpeg", 200),
        "tiny.jpg": ("image/jpeg", 200),
        "corrupt.jpg": ("image/jpeg", 422),
        "fake.png": ("image/png", 422),
        "note.txt": ("text/plain", 415),
        "anim.gif": ("image/gif", 415),
        "bomb.png": ("image/png", 422),
        "big.jpg": ("image/jpeg", 413),
    }
    docs: dict[str, list] = {}
    for name, (ctype, code) in expect.items():
        t0 = time.time()
        rr = owner.post(
            f"/api/projects/{pid}/documents",
            files=[("files", (name, (FIX / name).read_bytes(), ctype))],
        )
        check(
            "S8.14",
            f"upload {name} -> {code}",
            rr.status_code == code,
            f"{rr.status_code} {time.time() - t0:.1f}s {rr.text[:140] if rr.status_code != 200 else ''}",
        )
        if rr.status_code == 200:
            docs[name] = rr.json()["documents"]
    rr = owner.post(
        f"/api/projects/{pid}/documents",
        files=[
            (
                "files",
                (
                    "gas.heic",
                    (FIX / "gas.heic").read_bytes(),
                    "application/octet-stream",
                ),
            )
        ],
    )
    check(
        "S8.15",
        "HEIC sent as octet-stream is recognised by extension",
        rr.status_code == 200,
        str(rr.status_code),
    )
    check(
        "S8.16",
        "a 3-page PDF becomes 3 documents",
        len(docs.get("bills-3p.pdf", [])) == 3,
        str(len(docs.get("bills-3p.pdf", []))),
    )
    if not LIVE:
        rr = owner.post(
            f"/api/projects/{pid}/documents",
            files=[
                (
                    "files",
                    (
                        "bills-14p.pdf",
                        (FIX / "bills-14p.pdf").read_bytes(),
                        "application/pdf",
                    ),
                )
            ],
        )
        n14 = len(rr.json().get("documents", [])) if rr.status_code == 200 else 0
        note(
            "S8.17",
            f"a 14-page PDF -> {rr.status_code}, {n14} documents (cap 12, the rest silently dropped?)",
        )
    g = docs.get("gas.jpg", [{}])[0]
    rot = docs.get("rotated-exif6.jpg", [{}])[0]
    check(
        "S8.18",
        "EXIF orientation is applied (sideways photo comes out upright)",
        (rot.get("width"), rot.get("height")) == (g.get("width"), g.get("height")),
        f"{rot.get('width')}x{rot.get('height')} vs {g.get('width')}x{g.get('height')}",
    )
    for name, ds in docs.items():
        img = owner.get(f"/api/projects/{pid}/documents/{ds[0]['id']}/image")
        if not (img.status_code == 200 and img.content[:3] == b"\xff\xd8\xff"):
            check(
                "S8.19",
                f"stored image of {name} serves as JPEG",
                False,
                f"{img.status_code}",
            )
    check("S8.19", "every stored upload serves back as a JPEG", True)
    img = owner.get(f"/api/projects/{pid}/documents/{g['id']}/image")
    check(
        "S8.20",
        "a private project's photo is not publicly cacheable",
        "private" in img.headers.get("cache-control", ""),
        img.headers.get("cache-control", ""),
    )
    check(
        "S8.21",
        "a stranger cannot fetch a private project's photo",
        anon.get(
            f"/api/projects/{pid}/documents/{g['id']}/image", cookies={}
        ).status_code
        in (200, 401),
        "",
    )
    stranger = client()
    rr = stranger.get(f"/api/projects/{pid}/documents/{g['id']}/image")
    check(
        "S8.21b",
        "a stranger (no cookie) gets 401 for the photo",
        rr.status_code == 401,
        str(rr.status_code),
    )
    rr = owner.post(
        f"/api/projects/{pid}/documents",
        files=[
            (
                "files",
                (
                    "../../../../etc/evil name.jpg",
                    (FIX / "gas.jpg").read_bytes(),
                    "image/jpeg",
                ),
            )
        ],
    )
    check(
        "S8.22",
        "a path-like filename is stored safely",
        rr.status_code == 200,
        f"{rr.status_code} filename={rr.json()['documents'][0]['filename'] if rr.status_code == 200 else ''}",
    )
    rr = owner.post(
        f"/api/projects/{pid}/documents",
        files=[
            ("files", ("गैस बिल मार्च.jpg", (FIX / "gas.jpg").read_bytes(), "image/jpeg"))
        ],
    )
    check(
        "S8.23",
        "a Hindi filename uploads",
        rr.status_code == 200,
        f"{rr.status_code} {rr.json()['documents'][0]['filename'] if rr.status_code == 200 else rr.text[:100]}",
    )
    if not LIVE:
        many = [
            ("files", (f"g{i}.jpg", (FIX / "tiny.jpg").read_bytes(), "image/jpeg"))
            for i in range(41)
        ]
        rr = owner.post(f"/api/projects/{pid}/documents", files=many)
        n = len(rr.json().get("documents", [])) if rr.status_code == 200 else -1
        note(
            "S8.24", f"41 files in one request -> {rr.status_code}, {n} saved (cap 40)"
        )
        rr = owner.post(
            f"/api/projects/{pid}/documents",
            files=[
                ("files", ("ok.jpg", (FIX / "gas.jpg").read_bytes(), "image/jpeg")),
                ("files", ("bad.txt", b"x", "text/plain")),
            ],
        )
        after = C.get(f"/api/projects/{pid}", headers={"X-Pramaan-Key": key}).json()[
            "documents"
        ]
        note(
            "S8.25",
            f"mixed batch (good jpg + txt) -> {rr.status_code}; ok.jpg stored anyway: {any(x['filename'] == 'ok.jpg' for x in after)}",
        )
    rr = owner.post(f"/api/projects/{pid}/documents")
    check(
        "S8.26",
        "upload with no files -> 422",
        rr.status_code == 422,
        str(rr.status_code),
    )
    # product lines
    cn = owner.get("/api/refdata/cn/search", params={"q": "7318"}).json()
    note(
        "S8.27",
        f"CN search 7318 -> {len(cn)} results, first: {json.dumps(cn[:2])[:300]}",
    )
    good_cn = cn[0]["cn"] if cn else "73181568"
    line = {
        "name": "Hex bolts",
        "cn": good_cn,
        "precursor_name": "Wire rod",
        "precursor_cn": "72139110",
        "precursor_supplier": "Rod Mill (SAMPLE)",
    }
    rr = owner.put(f"/api/projects/{pid}/product-lines", json={"lines": [line]})
    check(
        "S8.28",
        "set one product line",
        rr.status_code == 200 and rr.json()["processes"],
        f"{rr.status_code} {rr.text[:200] if rr.status_code != 200 else ''}",
    )
    rr = owner.put(f"/api/projects/{pid}/product-lines", json={"lines": [line, line]})
    check("S8.29", "duplicate CN -> 422", rr.status_code == 422, str(rr.status_code))
    rr = owner.put(
        f"/api/projects/{pid}/product-lines",
        json={"lines": [{**line, "cn": "12345678"}]},
    )
    check(
        "S8.30",
        "a CN outside CBAM -> 422 with a reason",
        rr.status_code == 422,
        f"{rr.status_code} {rr.text[:200]}",
    )
    rr = owner.put(f"/api/projects/{pid}/product-lines", json={"lines": []})
    check("S8.31", "zero lines -> 422", rr.status_code == 422, str(rr.status_code))
    rr = owner.put(
        f"/api/projects/{pid}/product-lines",
        json={"lines": [{**line, "cn": c["cn"]} for c in (cn * 7)[:7]]},
    )
    check("S8.32", "seven lines -> 422", rr.status_code == 422, str(rr.status_code))
    rr = (
        owner.post(f"/api/projects/{pid}/product-lines/suggest")
        if not LIVE
        else httpx.Response(204)
    )
    if LIVE:
        note("S8.33", "suggest lines skipped on --live (it calls Gemini)")
    elif not state["health"]["models"]["gemini_configured"]:
        check(
            "S8.33",
            "suggest lines without Gemini -> 503",
            rr.status_code == 503,
            str(rr.status_code),
        )
    else:
        note(
            "S8.33", f"suggest lines (live Gemini) -> {rr.status_code} {rr.text[:300]}"
        )
    for body, code, why in (
        ({"months_to": 6}, 200, "period Jan-Jun"),
        ({"months_to": 13}, 200, "months_to 13 (clamped)"),
        ({"months_to": 0}, 200, "months_to 0 (clamped)"),
        ({"months_to": -4}, 200, "months_to -4 (clamped)"),
        ({"country": "Atlantis"}, 422, "unknown country"),
        ({"country": "China"}, 200, "country China"),
        ({"name": "   "}, 200, "blank name ignored"),
        (
            {"city": "<script>alert(1)</script>"},
            200,
            "script tag in city (stored as text)",
        ),
    ):
        rr = owner.patch(f"/api/projects/{pid}", json=body)
        check(
            "S8.34",
            f"patch own project: {why} -> {code}",
            rr.status_code == code,
            f"{rr.status_code} {rr.json().get('period_label', '') if rr.status_code == 200 else rr.text[:100]}",
        )
    rr = owner.post(f"/api/projects/{pid}/runs", json={"mode": "replay"})
    note("S8.35", f"replay run on an own project -> {rr.status_code} {rr.text[:200]}")
    if rr.status_code == 200:
        evs = sse_events(
            "GET",
            f"/api/projects/{pid}/runs/{rr.json()['run_id']}/events",
            cl=owner,
            max_s=120,
        )
        note(
            "S8.35b",
            f"own replay run end: {[e for e in evs if e[0] == 'end']} ({len(evs)} events); last: {json.dumps(evs[-2][1])[:300] if len(evs) > 1 else ''}",
        )
    # delete
    rr = C.delete(f"/api/projects/{state['demo2']}")
    check(
        "S8.36",
        "the sample cannot be deleted -> 403",
        rr.status_code == 403,
        str(rr.status_code),
    )
    rr = owner.delete(f"/api/projects/{pid}")
    check(
        "S8.37",
        "the owner deletes the project",
        rr.status_code == 200 and rr.json().get("deleted") == pid,
        rr.text[:200],
    )
    rr = owner.get(f"/api/projects/{pid}")
    check(
        "S8.38",
        "a deleted project is gone (404)",
        rr.status_code == 404,
        str(rr.status_code),
    )
    rr = owner.get(f"/api/projects/{pid}/documents/{g['id']}/image")
    check(
        "S8.39",
        "a deleted project's photos are gone",
        rr.status_code == 404,
        str(rr.status_code),
    )


# ---------------------------------------------------------------------------------------------- S9


@section("S9")
def s9():
    """reference data, golden EC example, metrics, copilot, try, voice"""
    r = C.get("/api/refdata/countries")
    check(
        "S9.1",
        "countries list",
        r.status_code == 200 and "India" in r.json() and len(r.json()) > 50,
        f"{len(r.json())} countries",
    )
    for q, why in (
        ("7318", "CN digits"),
        ("bolt", "a word"),
        ("", "empty"),
        ("'; DROP TABLE x;--", "SQL-ish"),
        ("<script>", "html"),
    ):
        r = C.get("/api/refdata/cn/search", params={"q": q})
        check(
            "S9.2",
            f"CN search {why}",
            r.status_code == 200,
            f"{r.status_code} {len(r.json()) if r.status_code == 200 else ''} results",
        )
    r = C.get("/api/refdata/cn/73181568")
    check("S9.3", "CN lookup", r.status_code == 200, r.text[:200])
    r = C.get("/api/refdata/cn/abc")
    note("S9.4", f"CN lookup 'abc' -> {r.status_code} {r.text[:150]}")
    r = C.get("/api/refdata")
    check(
        "S9.5",
        "refdata summary lists the official files",
        r.status_code == 200 and len(r.json()["files"]) >= 7,
        f"{len(r.json()['files'])} files",
    )
    t0 = time.time()
    r = C.get("/api/golden")
    g = r.json()
    check(
        "S9.6",
        "golden EC example check passes",
        r.status_code == 200
        and g.get("all_pass", g.get("passed")) not in (False, None),
        json.dumps({k: v for k, v in g.items() if not isinstance(v, (list, dict))})[
            :300
        ]
        + f" {time.time() - t0:.1f}s",
    )
    r = C.get("/api/metrics")
    m = r.json()
    check(
        "S9.7",
        "metrics (eval history) load",
        r.status_code == 200 and m.get("status") != "not_run",
        json.dumps({k: v for k, v in m.items() if not isinstance(v, (list, dict))})[
            :300
        ],
    )
    r = C.get("/api/copilot/examples")
    check(
        "S9.8",
        "copilot examples",
        r.status_code == 200 and len(r.json()) >= 3,
        str(len(r.json())),
    )
    for body, code, why in (
        ({"question": ""}, 422, "empty question"),
        ({"question": "x" * 501}, 422, "501-char question"),
        ({}, 422, "no question"),
    ):
        r = C.post("/api/copilot/ask", json=body)
        check(
            "S9.9",
            f"copilot: {why} -> {code}",
            r.status_code == code,
            str(r.status_code),
        )
    if not LIVE:
        r = C.post(
            "/api/copilot/ask",
            json={
                "question": "What is the default value for bolts from India?",
                "lang": "en",
            },
        )
        note("S9.10", f"copilot ask (no Gemini) -> {r.status_code} {r.text[:300]}")
        pid = state["demo"]
        r = C.post(
            f"/api/projects/{pid}/ask",
            json={
                "question": "Why is the buyer cost lower with our data?",
                "lang": "en",
            },
        )
        note("S9.11", f"report ask (no Gemini) -> {r.status_code} {r.text[:300]}")
    r = C.get("/api/try")
    t = r.json() if r.status_code == 200 else {}
    check(
        "S9.12",
        "/api/try status",
        r.status_code == 200 and len(t.get("samples", [])) == 3,
        json.dumps(t)[:300] if r.status_code == 200 else str(r.status_code),
    )
    for s in t.get("samples", []):
        r = C.get(f"/api/try/sample/{s['name']}/image")
        check(
            "S9.13",
            f"try sample image {s['name']}",
            r.status_code == 200
            and r.headers.get("content-type", "").startswith("image/"),
            f"{r.status_code} {len(r.content) // 1024} KB",
        )
    check(
        "S9.14",
        "try unknown sample image -> 404",
        C.get("/api/try/sample/nope/image").status_code in (404,) or LIVE,
    )
    if not LIVE and t:
        for s in t.get("samples", []):
            t0 = time.time()
            evs = sse_events("POST", f"/api/try/sample/{s['name']}")
            [e[0] for e in evs]
            stages = [e[1].get("stage") for e in evs]
            done = [e[1] for e in evs if e[1].get("stage") == "done"]
            check(
                "S9.15",
                f"try sample {s['name']} streams to done",
                done,
                f"{len(evs)} events {stages} {time.time() - t0:.1f}s; done={json.dumps(done[0])[:200] if done else None}",
            )
        r = C.post("/api/try/sample/nope")
        check(
            "S9.16",
            "try unknown sample -> 404",
            r.status_code == 404,
            str(r.status_code),
        )
        r = C.post(
            "/api/try",
            files={"file": ("gas.jpg", (FIX / "gas.jpg").read_bytes(), "image/jpeg")},
        )
        check(
            "S9.17",
            "try own photo without Gemini -> 503 with a message",
            r.status_code == 503,
            r.text[:150],
        )
        pid = state["demo"]
        r = C.post(
            f"/api/projects/{pid}/voice",
            data={"field_key": "scrap_t", "process": "P1", "period": "2026-03"},
            files={"audio": ("a.webm", b"\x1a\x45\xdf\xa3" + b"0" * 100, "audio/webm")},
        )
        check(
            "S9.18",
            "voice note without Gemini -> 503",
            r.status_code == 503,
            f"{r.status_code} {r.text[:100]}",
        )


# ---------------------------------------------------------------------------------------------- S10


@section("S10")
def s10():
    """call WebSocket refusals"""
    try:
        from websockets.sync.client import connect
    except ImportError:
        note("S10", "websockets not installed")
        return
    ws_base = BASE.replace("https://", "wss://").replace("http://", "ws://")
    BASE.split("://", 1)[1]

    def call(
        path: str, origin: str | None = None, cookie: str | None = None
    ) -> tuple[object, object]:
        headers = {}
        if origin:
            headers["Origin"] = origin
        if cookie:
            headers["Cookie"] = cookie
        try:
            with connect(
                ws_base + path,
                additional_headers=headers,
                open_timeout=20,
                close_timeout=5,
            ) as ws:
                msg = ws.recv(timeout=20)
                try:
                    ws.recv(timeout=5)
                except Exception:
                    pass
                return json.loads(msg) if isinstance(msg, str) else msg, ws.close_code
        except Exception as exc:
            return f"{exc.__class__.__name__}: {exc}", None

    msg, code = call("/api/projects/nope/call", origin=BASE)
    check(
        "S10.1",
        "call: unknown project -> not_found 4404",
        isinstance(msg, dict) and msg.get("code") == "not_found",
        f"{msg} {code}",
    )
    msg, code = call(
        f"/api/projects/{state['demo']}/call", origin="https://evil.example"
    )
    check(
        "S10.2",
        "call: a foreign page cannot open a call -> origin 4403",
        isinstance(msg, dict) and msg.get("code") == "origin",
        f"{msg} {code}",
    )
    if "own" in state:
        pass
    owner = client()
    d = owner.post(
        "/api/projects", json={"name": "QA call", "company": "QA (SAMPLE)"}
    ).json()
    msg, code = call(f"/api/projects/{d['id']}/call", origin=BASE)
    check(
        "S10.3",
        "call: a private project without its passcode -> private 4401",
        isinstance(msg, dict) and msg.get("code") == "private",
        f"{msg} {code}",
    )
    msg, code = call(
        f"/api/projects/{d['id']}/call",
        origin=BASE,
        cookie=f"pk_{d['id']}={d['access_key'].replace('-', '')}",
    )
    expect = (
        "no_gemini"
        if not state["health"]["models"]["gemini_configured"]
        else "no_report"
    )
    check(
        "S10.4",
        f"call: the owner's project with no report -> {expect}",
        isinstance(msg, dict) and msg.get("code") == expect,
        f"{msg} {code}",
    )
    owner.delete(f"/api/projects/{d['id']}")
    if not state["health"]["models"]["gemini_configured"]:
        msg, code = call(f"/api/projects/{state['demo']}/call", origin=BASE)
        check(
            "S10.5",
            "call without Gemini -> no_gemini 4503",
            isinstance(msg, dict) and msg.get("code") == "no_gemini",
            f"{msg} {code}",
        )


# ---------------------------------------------------------------------------------------------- S11


@section("S11")
def s11():
    """robustness: concurrency, odd inputs, error shapes"""
    pid = C.post("/api/demo/load", json={}).json()["project_id"]
    codes: list[int] = []

    def go():
        codes.append(
            client()
            .post(f"/api/projects/{pid}/runs", json={"mode": "replay"})
            .status_code
        )

    ts = [threading.Thread(target=go) for _ in range(4)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    check(
        "S11.1",
        "4 simultaneous run starts: exactly one runs",
        sorted(codes).count(200) == 1,
        f"codes={sorted(codes)}",
    )
    time.sleep(1)
    runs = C.get(f"/api/projects/{pid}/runs").json()
    note("S11.1b", f"runs now: {[(x['status'], x['mode']) for x in runs]}")
    for _ in range(60):
        if not C.get(f"/api/projects/{pid}").json()["running"]:
            break
        time.sleep(2)
    for m, u, body in (
        ("POST", "/api/projects", [1, 2]),
        ("POST", "/api/projects", {"name": 5, "company": None}),
        ("PATCH", f"/api/projects/{pid}", {"fx_inr_per_eur": 5}),
        ("POST", f"/api/projects/{pid}/whatif", {"process_id": None}),
        ("POST", "/api/copilot/ask", {"question": ["a"]}),
        ("PUT", f"/api/projects/{pid}/product-lines", {"lines": "x"}),
    ):
        r = C.request(m, u, json=body)
        check(
            "S11.2",
            f"{m} {u.replace(pid, '{pid}')} with wrong types -> 4xx (not 500)",
            400 <= r.status_code < 500,
            f"{r.status_code} {r.text[:120]}",
        )
    r = C.post(
        "/api/projects",
        content=b"x" * (2 * 1024 * 1024),
        headers={"content-type": "application/json"},
    )
    check(
        "S11.3",
        "2 MB garbage JSON -> 4xx",
        400 <= r.status_code < 500,
        str(r.status_code),
    )
    r = C.get("/api/projects/" + "a" * 3000)
    check(
        "S11.4",
        "a 3000-char project id -> 4xx",
        400 <= r.status_code < 500,
        str(r.status_code),
    )
    r = C.get("/api/projects/..%2F..%2Fetc%2Fpasswd")
    check(
        "S11.5",
        "encoded traversal in the project id -> 404",
        r.status_code in (404, 401),
        str(r.status_code),
    )
    r = C.get("/api/projects/%00")
    check(
        "S11.6",
        "NUL in the project id -> 4xx",
        400 <= r.status_code < 500,
        str(r.status_code),
    )
    r = C.get("/..%2F..%2F..%2Fetc%2Fpasswd")
    check(
        "S11.7",
        "traversal on the static route does not leak files",
        "root:" not in r.text,
        str(r.status_code),
    )
    r = C.get("/%2e%2e/%2e%2e/backend/app/config.py")
    check(
        "S11.8",
        "dot-dot on the static route does not serve source",
        "def settings" not in r.text,
        str(r.status_code),
    )
    r = C.options(
        "/api/projects",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    note(
        "S11.9",
        f"CORS preflight from a foreign origin -> {r.status_code}, allow-origin={r.headers.get('access-control-allow-origin')}",
    )
    r = C.post("/api/demo/load", json={}, headers={"Origin": "https://evil.example"})
    note(
        "S11.10",
        f"cross-origin POST demo/load -> {r.status_code} allow-origin={r.headers.get('access-control-allow-origin')}",
    )


# ---------------------------------------------------------------------------------------------- S12


@section("S12")
def s12():
    """rate limits (local only)"""
    if LIVE:
        return
    hits = [C.post("/api/try/sample/gas-2026-03").status_code for _ in range(25)]
    note("S12.1", f"25 /try sample reads from one address -> {hits}")
    if 429 in hits:
        r = C.post(
            "/api/try/sample/gas-2026-03", headers={"X-Forwarded-For": "203.0.113.9"}
        )
        note(
            "S12.2",
            f"after the cap, the same client with a made-up X-Forwarded-For -> {r.status_code} (200 = the cap can be dodged)",
        )
    p = client().post("/api/projects", json={"name": "rl", "company": "rl"}).json()
    codes = [
        client()
        .post(f"/api/projects/{p['id']}/unlock", json={"passcode": "WRONG"})
        .status_code
        for _ in range(22)
    ]
    first = codes.index(429) if 429 in codes else -1
    check(
        "S12.3",
        "unlock: wrong passcodes are capped (20 an hour per address, earlier attempts count)",
        first >= 0 and all(c == 429 for c in codes[first:]),
        f"first 429 at attempt {first + 1}: {codes}",
    )
    r = client().post(
        f"/api/projects/{p['id']}/unlock",
        json={"passcode": "WRONG"},
        headers={"X-Forwarded-For": "198.51.100.7"},
    )
    note(
        "S12.4",
        f"unlock after the cap with a made-up X-Forwarded-For -> {r.status_code} (401 = cap dodged)",
    )


if __name__ == "__main__":
    for fn in (s1, s2, s3, s4, s5, s6, s7, s8, s9, s10, s11, s12):
        fn()
    fails = [r for r in results if not r[2]]
    print(
        f"\n{len([r for r in results if r[3] != 'NOTE'])} checks, {len(fails)} failed"
    )
    for f in fails:
        print("  FAIL", f[0], f[1], f[3][:300])
    sys.exit(1 if fails else 0)
