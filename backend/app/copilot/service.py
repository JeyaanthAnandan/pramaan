"""S1 / USP 8: Rules copilot with page-number citations.

Backends (chosen automatically):
  * file_search - Gemini File Search store (Gemini Developer API mode; FILE_SEARCH_STORE set)
  * grounded    - page-level BM25 retrieval over the official EC guidance PDFs, then Gemini 3.8
                  Flash answers ONLY from the retrieved pages and cites them (works on Agent Platform)
  * retrieval   - no Gemini configured: returns the best passages with their page numbers
Citations are validated: a cited page must be one of the retrieved/grounding pages.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from app.config import settings

DOCS = {
    "guidance_1_introduction.pdf": "Guidance 1",
    "guidance_2_quick_guide_non_eu_operators.pdf": "Guidance 2",
    "guidance_3_calculation_methods.pdf": "Guidance 3",
    "guidance_4_free_allocation_adjustment.pdf": "Guidance 4",
    "guidance_5d_iron_and_steel.pdf": "Guidance 5d",
}
EXAMPLES = [
    "Does electricity count for my screws?",
    "What if my rod supplier won't share data?",
    "What extra parameters must I report for screws?",
    "When is the first declaration due?",
    "Is scrap counted?",
]
EXPAND = {
    "electricity": ["indirect", "direct", "only", "taken", "account", "annex"],
    "count": ["taken", "account", "only"],
    "screws": ["iron", "steel", "products", "7318"],
    "screw": ["iron", "steel", "products"],
    "bolts": ["iron", "steel", "products"],
    "supplier": ["precursor", "default", "values", "verified"],
    "share": ["data", "default", "precursor"],
    "won't": ["default", "values"],
    "declaration": ["declarant", "september", "surrender", "annual"],
    "due": ["deadline", "september", "year"],
    "scrap": ["zero", "embedded", "emissions", "waste"],
    "extra": ["additional", "parameters", "reporting", "requirement"],
    "parameters": ["additional", "reducing", "agent", "alloy"],
    "counted": ["zero", "embedded"],
}
PHRASES = {
    "electricity": ["only direct emissions", "indirect emissions"],
    "scrap": ["zero embedded emissions", "scrap"],
    "supplier": ["default values", "verified data"],
    "declaration": ["30 september", "cbam declaration"],
    "extra": ["additional iron and steel sector parameters", "reporting requirement"],
}


def _topic(q: str) -> str:
    ql = q.lower()
    for key in PHRASES:
        if key in ql or (key == "supplier" and "share data" in ql) or (key == "extra" and "parameter" in ql):
            return key
    return ""


STOP = set(
    "a an the of to in for and or is are be my me i we our do does what if when how which with on by at as it this that won t s".split()
)


@dataclass
class Chunk:
    doc: str
    page: int
    text: str
    tokens: list[str]


def _tok(s: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9']+", s.lower().replace("’", "'")) if t not in STOP and len(t) > 1]


@lru_cache(maxsize=1)
def corpus() -> list[Chunk]:
    cache = settings().data_dir / "copilot_corpus.json"
    pages: list[dict[str, Any]] = []
    if cache.exists():
        pages = json.loads(cache.read_text())
    else:
        import pypdf

        for fname, label in DOCS.items():
            path = settings().regulation_dir / fname
            if not path.exists():
                continue
            for i, pg in enumerate(pypdf.PdfReader(str(path)).pages):
                text = re.sub(r"[ \t]+", " ", pg.extract_text() or "").strip()
                if len(text) > 80:
                    pages.append({"doc": label, "page": i + 1, "text": text})
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(pages))
    chunks = []
    for p in pages:
        paras = re.split(r"\n\s*\n", p["text"])
        buf = ""
        for para in paras:
            if len(buf) + len(para) > 1400 and buf:
                chunks.append(Chunk(p["doc"], p["page"], buf.strip(), _tok(buf)))
                buf = ""
            buf += para + "\n"
        if buf.strip():
            chunks.append(Chunk(p["doc"], p["page"], buf.strip(), _tok(buf)))
    return chunks


@lru_cache(maxsize=1)
def _idf() -> tuple[dict[str, float], float]:
    cs = corpus()
    df: Counter[str] = Counter()
    for c in cs:
        df.update(set(c.tokens))
    n = len(cs) or 1
    avg = sum(len(c.tokens) for c in cs) / n
    return {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}, avg


def retrieve(question: str, k: int = 6) -> list[dict[str, Any]]:
    q = _tok(question)
    q += [x for t in list(q) for x in EXPAND.get(t, [])]
    idf, avg = _idf()
    scored = []
    for c in corpus():
        tf = Counter(c.tokens)
        dl = len(c.tokens) or 1
        s = 0.0
        for t in q:
            if t in tf:
                s += idf.get(t, 0) * tf[t] * 2.2 / (tf[t] + 1.2 * (0.25 + 0.75 * dl / avg))
        if c.doc == "Guidance 5d":
            s *= 1.15  # sector guidance first for a steel-goods exporter
        low = c.text.lower()
        s += sum(4.0 for ph in PHRASES.get(_topic(question), []) if ph in low)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for s, c in scored:
        key = (c.doc, c.page)
        if key in seen:
            continue
        seen.add(key)
        out.append({"doc": c.doc, "page": c.page, "score": round(s, 2), "text": c.text[:1400], "snippet": _snippet(c.text, q)})
        if len(out) >= k:
            break
    return out


def _snippet(text: str, q: list[str]) -> str:
    sents = re.split(r"(?<=[.;:])\s+", text.replace("\n", " "))
    best = max(sents, key=lambda s: sum(1 for t in set(q) if t in s.lower()), default="")
    return best[:420]


CITE_RX = re.compile(r"\[(Guidance (?:1|2|3|4|5d)),?\s*p\.?\s*(\d+)\]")


def _validate(answer: str, allowed: set[tuple[str, int]]) -> tuple[list[dict[str, Any]], list[str]]:
    cites: list[dict[str, Any]] = []
    bad: list[str] = []
    for m in CITE_RX.finditer(answer):
        key = (m.group(1), int(m.group(2)))
        if key not in allowed:
            bad.append(f"{key[0]} p.{key[1]}")
        elif {"doc": key[0], "page": key[1]} not in cites:
            cites.append({"doc": key[0], "page": key[1]})
    return cites, bad


async def answer(question: str, lang: str = "en") -> dict[str, Any]:
    cfg = settings()
    passages = retrieve(question)
    if not cfg.gemini_configured:
        return {
            "mode": "retrieval",
            "answer": None,
            "note": "Gemini is not configured on this server: showing the most relevant pages of the official guidance.",
            "citations": [{"doc": p["doc"], "page": p["page"]} for p in passages[:4]],
            "passages": passages[:4],
        }
    from app.agents.llm import gemini, text_part

    lang_line = {"hi": "Answer in Hindi.", "ta": "Answer in Tamil.", "vi": "Answer in Vietnamese."}.get(lang, "Answer in English.")
    system = (
        "You answer EU CBAM questions for a small Indian steel-goods exporter (fasteners). Use ONLY the provided guidance pages. "
        "Cite every claim with [Guidance N, p. X] using exactly the doc and page labels given. If the pages do not answer the question, say so. "
        "Keep regulatory terms (SEE, SEFA, CBAM, CN, default value) in English. Max 120 words. " + lang_line
    )
    ctx = "\n\n".join(f'<page doc="{p["doc"]}" page="{p["page"]}">\n{p["text"]}\n</page>' for p in passages)
    r = await gemini().text(cfg.model_flash, system, [text_part(f"{ctx}\n\nQuestion: {question}")], thinking_level="low")
    text = str(r.data)
    cites, bad = _validate(text, {(p["doc"], p["page"]) for p in passages})
    return {
        "mode": "grounded",
        "model": r.model,
        "answer": text,
        "citations": cites,
        "invalid_citations": bad,
        "passages": passages[:4],
        "tokens": {"in": r.tokens_in, "out": r.tokens_out},
    }
