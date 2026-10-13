"""Several judges at once: N visitors each open the landing page, load the sample, open the report data
and download the PDF; prints p50/p95/max per step and the status codes. No Gemini is called.

    backend/.venv/bin/python scripts/qa/load_check.py https://<service>.run.app 5
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time

import httpx

B, N = sys.argv[1].rstrip("/"), int(sys.argv[2]) if len(sys.argv) > 2 else 5
STEPS = ("/", "load", "project", "results", "evidence", "pdf")


async def visitor(stats: dict[str, list[tuple[float, int]]]) -> None:
    async with httpx.AsyncClient(base_url=B, timeout=120) as c:
        t0 = time.time()
        r = await c.get("/")
        stats["/"].append((time.time() - t0, r.status_code))
        t0 = time.time()
        r = await c.post("/api/demo/load", json={})
        stats["load"].append((time.time() - t0, r.status_code))
        if r.status_code != 200:
            return
        pid = r.json()["project_id"]
        for name, path in (
            ("project", f"/api/projects/{pid}"),
            ("results", f"/api/projects/{pid}/results"),
            ("evidence", f"/api/projects/{pid}/evidence"),
            ("pdf", f"/api/projects/{pid}/export/pdf"),
        ):
            t0 = time.time()
            r = await c.get(path)
            stats[name].append((time.time() - t0, r.status_code))


async def main() -> None:
    stats: dict[str, list[tuple[float, int]]] = {k: [] for k in STEPS}
    t0 = time.time()
    await asyncio.gather(*(visitor(stats) for _ in range(N)))
    print(f"{N} visitors in {time.time() - t0:.1f}s")
    for k, v in stats.items():
        if not v:
            continue
        ts = sorted(x[0] for x in v)
        codes: dict[int, int] = {}
        for _, s in v:
            codes[s] = codes.get(s, 0) + 1
        print(
            f"  {k:9} n={len(v):3} p50={statistics.median(ts):5.2f}s p95={ts[int(0.95 * (len(ts) - 1))]:5.2f}s max={ts[-1]:5.2f}s codes={codes}"
        )


asyncio.run(main())
