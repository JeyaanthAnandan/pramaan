"""Run the new factory through the live service: own private project, Jan-Jun, 16 photos, live Gemini."""
import json, sys, time
from pathlib import Path
import httpx
B = sys.argv[1]
c = httpx.Client(base_url=B, timeout=900)
p = c.post("/api/projects", json={"name": "Kaveri QA run (TEST)", "company": "Kaveri Precision Fasteners Pvt Ltd (TEST — fictional)", "city": "Coimbatore", "country": "India", "months_to": 6}).json()
pid, key = p["id"], p["access_key"]
print("project", pid, "passcode", key, "period", p.get("period_label"))
json.dump({"pid": pid, "key": key}, open("live_project.json", "w"))
files = sorted(Path("out").glob("*.jpg"))
t0 = time.time()
r = c.post(f"/api/projects/{pid}/documents", files=[("files", (f.name, f.read_bytes(), "image/jpeg")) for f in files])
print("upload", r.status_code, len(r.json().get("documents", [])), f"documents in {time.time() - t0:.1f}s")
t0 = time.time()
r = c.post(f"/api/projects/{pid}/runs", json={"mode": "live", "lang": "en"})
print("run", r.status_code, r.text[:120])
rid = r.json()["run_id"]
events = []
with c.stream("GET", f"/api/projects/{pid}/runs/{rid}/events") as s:
    ev = None
    for line in s.iter_lines():
        if line.startswith("event:"):
            ev = line[6:].strip()
        elif line.startswith("data:"):
            d = json.loads(line[5:])
            events.append((ev, d))
            if ev == "timeline" and d.get("status") in ("done", "error", "review") and d.get("agent") not in ("Extractor", "Classifier"):
                print(f"  {time.time() - t0:6.1f}s {d.get('agent')} [{d.get('status')}] {str(d.get('output_summary'))[:160]}", flush=True)
            if ev == "end":
                print(f"end after {time.time() - t0:.1f}s", json.dumps(d)[:500])
                break
json.dump(events, open("live_events.json", "w"), ensure_ascii=False)
for name, path in (("project", f"/api/projects/{pid}"), ("evidence", f"/api/projects/{pid}/evidence"), ("results", f"/api/projects/{pid}/results")):
    r = c.get(path)
    json.dump(r.json() if r.status_code == 200 else {"status": r.status_code, "text": r.text}, open(f"live_{name}.json", "w"), ensure_ascii=False, indent=1)
    print(name, r.status_code)
