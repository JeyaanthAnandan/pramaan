"""Call Pramaan: a voice call about the factory's own report (Gemini Live).

The owner taps Call and talks, in English, Hindi, Punjabi, Tamil or Vietnamese, as on a phone
call: "how much does my data save my buyer?", "show me where the gas figure comes from". The
browser streams the microphone to this server (16 kHz PCM) and plays the answer (24 kHz PCM). The
server holds the Gemini Live session, so no credential reaches the browser.

The rules are the same as for the written "Ask about this report":

* The agent answers from FACTS, the deterministic engine's figures (each with its calculation-tree
  node), and may not compute. Its tools give it a figure's formula and inputs with the document
  each input was read from, the EC guidance pages, and the open items.
* Every number it *says* is checked against the report, from the transcript of its own audio.
  Matched figures appear on screen as cards that open the Evidence Lens; a number that is not in
  the report is flagged on screen and never shown as a fact.
* It can drive the screen: open_evidence opens the Evidence Lens on the figure being discussed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.agents.explainer import _allowed_numbers, _strip_refs, numbers_in
from app.config import settings
from app.copilot.report import facts, focus
from app.evidence.models import Project

log = logging.getLogger("pramaan.call")

LANGS = {"en": "English", "hi": "Hindi", "pa": "Punjabi", "ta": "Tamil", "vi": "Vietnamese"}
# The call's language is set on the session: with the language only in the instruction, a Punjabi or
# Vietnamese call was greeted in English (live test, 2026-10-13). A language on the *transcription*
# is left unset: with hi-IN there, the transcript spelled 409,545 out in Hindi words.
SPEECH_CODES = {"en": "en-IN", "hi": "hi-IN", "pa": "pa-IN", "ta": "ta-IN", "vi": "vi-VN"}
IN_RATE, OUT_RATE = 16_000, 24_000  # PCM16 mono: microphone in, voice out
MAX_FRAME = 64 * 1024  # one microphone frame is ~3 KB (100 ms); anything far larger is not audio from our page
IDLE_S = 90.0  # no audio or text from the caller for this long ends the call

TOOLS: list[dict[str, Any]] = [
    {
        "name": "explain_number",
        "description": "How one figure from FACTS is worked out: its formula and the values behind it, each with the document "
        "it was read from. Use it for 'why', 'how' and 'where does it come from' questions.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {"fact_id": {"type": "string", "description": "a fact id from FACTS, e.g. P1.see"}},
            "required": ["fact_id"],
        },
    },
    {
        "name": "open_evidence",
        "description": "Show the caller, on their screen, where a figure comes from: the Evidence Lens with its formula and "
        "the highlighted value on the original document photo. Use it when the caller asks to see or show something.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {"fact_id": {"type": "string", "description": "a fact id from FACTS, e.g. verdict.secured"}},
            "required": ["fact_id"],
        },
    },
    {
        "name": "search_guidance",
        "description": "Search the European Commission's official CBAM guidance (what counts, deadlines, default values, "
        "verification). Returns passages with their document and page, to name in the answer.",
        "parameters_json_schema": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
    {
        "name": "open_items",
        "description": "What still needs the owner's attention: values waiting for a check, missing documents, product lines "
        "still on EU default values.",
    },
]


@dataclass
class CallContext:
    """One call's view of the report: the facts the agent may say and the tree they come from."""

    project: Project
    result: dict[str, Any]
    facts: list[dict[str, Any]]
    by_id: dict[str, dict[str, Any]]
    allowed: set[Decimal]
    tools_used: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)

    @classmethod
    def build(cls, project: Project, result: dict[str, Any]) -> CallContext:
        fs = facts(project, result)
        pseudo = {
            f["id"]: {"value": f["value"].replace(",", ""), "display": f["value"].replace(",", ""), "unit": f["unit"] or "x"} for f in fs
        }
        return cls(project, result, fs, {f["id"]: f for f in fs}, _allowed_numbers({**result["calc_tree"], **pseudo}))

    def node_of(self, fact_id: str) -> str | None:
        """The Evidence Lens node of a fact id (or of a calculation-tree node named directly)."""
        f = self.by_id.get(fact_id)
        if f:
            return f.get("node")
        return fact_id if fact_id in self.result["calc_tree"] else None


def system_instruction(ctx: CallContext, lang: str) -> str:
    p = ctx.project
    language = LANGS.get(lang, "English")
    terms = " Keep the terms SEE, CBAM, CN, EU and EUR in English." if lang in {"hi", "pa", "ta", "vi"} else ""
    fact_lines = "\n".join(f"- {f['id']}: {f['label']} = {f['value']}{(' ' + f['unit']) if f['unit'] else ''}" for f in ctx.facts)
    return (
        f"You are Pramaan, on a voice call with the owner of {p.company}{f', {p.city}' if p.city else ''}, a small steel-goods "
        f"exporter. You have their CBAM report open.\n"
        f"Speak {language}. If the caller switches language, switch with them.{terms}\n"
        "Rules:\n"
        "- Answer ONLY from FACTS below and from your tools. Never compute, convert, round or add up numbers: say each figure "
        "exactly as written in FACTS, with its unit, and keep it in that form (409,545 EUR, not words). If the answer needs a "
        "figure that is not there, say which document or data is missing.\n"
        "- This is a phone call: one to three short sentences in plain words. No lists, no markdown, never read out fact ids.\n"
        "- 'Why', 'how' or 'where does it come from': call explain_number. 'Show me': call open_evidence. EU rules: call "
        "search_guidance and name the guidance and page. 'What is left to do': call open_items.\n"
        "- Money: say euros as written. Give rupees too when the caller asks for rupees or speaks Hindi, Punjabi or Tamil.\n"
        "- You cannot change, approve or send anything on this call: the owner does that on screen.\n"
        f"FACTS (id: label = value unit):\n{fact_lines}"
    )


def greeting(ctx: CallContext, lang: str) -> str:
    return (
        f"(The call has just started. Greet the caller in {LANGS.get(lang, 'English')} in one short sentence as Pramaan, say "
        f"you have the {ctx.project.company} report open, and ask what they would like to know.)"
    )


# ------------------------------------------------------------------ tools (deterministic, no model)


def run_tool(name: str, args: dict[str, Any], ctx: CallContext) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """The tool's answer for the model, and an optional action for the caller's screen."""
    ctx.tools_used.append(name)
    if name in {"explain_number", "open_evidence"}:
        fid = str(args.get("fact_id") or "")
        node = ctx.node_of(fid)
        f = ctx.by_id.get(fid)
        if name == "open_evidence":
            if not node:
                return {"shown": False, "reason": "this figure has no proof page of its own; explain_number lists its parts"}, None
            ctx.shown.append(node)
            label = f["label"] if f else ctx.result["calc_tree"][node]["label"]
            return {"shown": True, "figure": label}, {"type": "action", "name": "open_evidence", "node": node, "label": label}
        if not node:
            return (
                {"figure": f, "inputs": [], "note": "a total of the figures listed in FACTS"} if f else {"error": f"unknown fact id {fid}"}
            ), None
        rows = focus(ctx.result, node)
        out = [{"label": r["label"], "value": r["value"], "unit": r["unit"]} for r in rows]
        return {"figure": out[0] if out else None, "inputs": out[1:]}, None
    if name == "search_guidance":
        from app.copilot.service import retrieve

        q = str(args.get("question") or "")[:300]
        return {"passages": [{"doc": p["doc"], "page": p["page"], "text": p["text"][:900]} for p in retrieve(q, k=3)]}, None
    if name == "open_items":
        names = {p.id: p.name for p in ctx.project.processes}
        items = [
            {
                "what": g["kind"].replace("_", " "),
                "status": "missing or on EU defaults" if g["status"] == "red" else "needs a check",
                "product_line": names.get(g.get("process") or "", ""),
                **{
                    k: v
                    for k, v in (g.get("params") or {}).items()
                    if k in {"label", "first", "second", "supplier", "precursor", "missing"}
                },
            }
            for g in ctx.result.get("gaps", [])
            if g["status"] in ("red", "amber")
        ]
        return {"open_items": items[:12], "count": len(items)}, None
    return {"error": f"unknown tool {name}"}, None


# ------------------------------------------------------------------ numbers guard on speech

# Devanagari, Gurmukhi and Tamil digits, in case the transcript writes them
_DIGITS = str.maketrans("०१२३४५६७८९੦੧੨੩੪੫੬੭੮੯௦௧௨௩௪௫௬௭௮௯", "0123456789" * 3)


def _num(text: str) -> Decimal | None:
    try:
        return Decimal(text.replace(",", "").lstrip("+").strip())
    except (InvalidOperation, AttributeError):
        return None


_UNITS = {
    w: i
    for i, w in enumerate(
        "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen".split()
    )
}
_TENS = {w: 10 * i for i, w in enumerate("_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()) if w != "_"}
_SCALES = {"thousand": 10**3, "lakh": 10**5, "lakhs": 10**5, "million": 10**6, "crore": 10**7, "crores": 10**7, "billion": 10**9}
_WORD = re.compile(r"[A-Za-z]+|[^A-Za-z]+")


def words_to_digits(text: str) -> str:
    """English number words as digits ("four hundred nine thousand five hundred forty-five" ->
    "409545", "eight point six nine three" -> "8.693"): the transcript of a spoken answer sometimes
    spells figures out, and the numbers guard reads digits."""
    out: list[str] = []
    run: list[str] = []

    def flush() -> None:
        while run and run[-1] in {"and", "point"}:  # "...and" / "...point" at the end is a word
            tail = run.pop()
            _emit()
            out.append(f" {tail}")
            return
        _emit()

    def _emit() -> None:
        if not run:
            return
        total, cur, frac, in_frac = 0, 0, "", False
        for w in run:
            if w == "point":
                in_frac = True
            elif in_frac:
                frac += str(_UNITS.get(w, 0)) if w in _UNITS and _UNITS[w] < 10 else ""
            elif w in _UNITS:
                cur += _UNITS[w]
            elif w in _TENS:
                cur += _TENS[w]
            elif w == "hundred":
                cur = (cur or 1) * 100
            elif w in _SCALES:
                total += (cur or 1) * _SCALES[w]
                cur = 0
        out.append(f"{total + cur}" + (f".{frac}" if frac else ""))
        run.clear()

    for tok in _WORD.findall(text.replace("-", " ")):
        w = tok.lower()
        is_num = w in _UNITS or w in _TENS or w == "hundred" or w in _SCALES
        if is_num or (run and w in {"and", "point"}):
            if w == "point" and "point" in run:
                flush()
            run.append(w)
        elif run and tok.isspace():
            continue  # spaces inside a number
        else:
            flush()
            out.append(tok if not out or not out[-1][-1:].isdigit() or tok[:1].isspace() else f" {tok}")
    flush()
    return "".join(out)


async def spoken_digits(text: str, lang: str) -> str:
    """The transcript with its number words as digits. English is converted by words_to_digits.
    Other languages go through Gemini Flash-Lite once the turn is over: a Punjabi answer said
    "ਚਾਰ ਲੱਖ ਨੌਂ ਹਜ਼ਾਰ ਪੰਜ ਸੌ ਪੰਤਾਲੀ EUR" (409,545) in the live test. It only rewrites words as
    digits; the deterministic check below decides what is in the report. Without an answer the
    transcript is checked as it is (a figure in words then simply shows no card). What comes back
    is used for cards only, never for the not-in-the-report warning (see report_turn)."""
    t = words_to_digits(text.translate(_DIGITS))
    if lang == "en" or not t.strip():
        return t
    from app.agents.llm import gemini, text_part

    try:
        r = await gemini().text(
            settings().model_lite,
            "Rewrite every number written in words as digits, for example चार लाख नौ हज़ार पाँच सौ पैंतालीस -> 409545 and "
            "आठ दशमलव छह नौ तीन -> 8.693. Change nothing else. Output only the text.",
            [text_part(t)],
            thinking_level="minimal",
        )
    except Exception as exc:
        log.warning("call: digits rewrite failed (%s)", str(exc)[:120] or exc.__class__.__name__)
        return t
    out = str(r.data or "").strip()
    return out if out and len(out) < 2 * len(t) + 40 else t


def check_spoken(text: str, ctx: CallContext) -> tuple[list[dict[str, Any]], list[str]]:
    """Figures from the report that the agent said (in order, once each) and numbers it said that
    are not in the report. Years, small counts and page numbers pass as in the written guard."""
    said: list[dict[str, Any]] = []
    bad: list[str] = []
    for n in numbers_in(_strip_refs(words_to_digits(text.translate(_DIGITS)))):
        hits = [f for f in ctx.facts if (v := _num(f["value"])) is not None and v == n]
        hits.sort(key=lambda f: f.get("node") is None)  # a figure with a proof page first
        if hits:
            if hits[0] not in said:
                said.append(hits[0])
        elif n not in ctx.allowed and n.normalize() not in ctx.allowed:
            bad.append(str(n))
    return said, bad


async def turn_figures(said: str, lang: str, ctx: CallContext) -> tuple[list[dict[str, Any]], list[str]]:
    """The figures one spoken answer used, and the numbers in it that are not in the report."""
    figures, bad = check_spoken(said, ctx)
    if lang != "en":
        # Numbers rebuilt from words by the model may add a card, never a warning: in a live Punjabi
        # test the transcript itself garbled the spoken words (ਪੰਜ ਸੌਤਾਲੀ), and the rewrite of a
        # correct figure did not match the report.
        more, _ = check_spoken(await spoken_digits(said, lang), ctx)
        figures += [f for f in more if f not in figures]
    return figures, bad


# ------------------------------------------------------------------ the live session


def live_config(ctx: CallContext, lang: str) -> Any:
    from google.genai import types

    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=system_instruction(ctx, lang),
        tools=[types.Tool(function_declarations=[types.FunctionDeclaration(**t) for t in TOOLS])],
        speech_config=types.SpeechConfig(language_code=SPEECH_CODES.get(lang, "en-IN")),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )


def connect(config: Any) -> AbstractAsyncContextManager[Any]:
    """A Gemini Live session: Agent Platform with the service account in production, the Developer
    API key locally. Tests replace this function with a scripted session."""
    from google import genai

    cfg = settings()
    if cfg.gemini_mode == "api_key":
        client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    else:
        client = genai.Client(vertexai=True, project=cfg.gcp_project, location=cfg.live_location)
    return client.aio.live.connect(model=cfg.model_live, config=config)


async def bridge(caller: Any, ctx: CallContext, lang: str) -> dict[str, Any]:
    """Run one call until the caller hangs up, the session ends or the time limit is reached.
    ``caller`` is the browser's WebSocket (receive / send_json / send_bytes)."""
    from google.genai import types

    cfg = settings()
    stats: dict[str, Any] = {"turns": 0, "unverified": 0, "figures": 0, "ended": "hangup"}
    t0 = time.monotonic()
    last_heard = [time.monotonic()]

    async with connect(live_config(ctx, lang)) as session:
        await caller.send_json({"type": "ready", "model": cfg.model_live, "lang": lang, "max_seconds": cfg.call_max_seconds})
        await session.send_realtime_input(text=greeting(ctx, lang))

        async def uplink() -> None:
            while True:
                msg = await caller.receive()
                if msg.get("type") == "websocket.disconnect":
                    return
                if (data := msg.get("bytes")) is not None:
                    if 0 < len(data) <= MAX_FRAME and len(data) % 2 == 0:
                        last_heard[0] = time.monotonic()
                        await session.send_realtime_input(audio=types.Blob(data=data, mime_type=f"audio/pcm;rate={IN_RATE}"))
                    continue
                try:
                    m = json.loads(msg.get("text") or "{}")
                except json.JSONDecodeError:
                    continue
                if m.get("type") == "hangup":
                    return
                if m.get("type") == "text" and (q := str(m.get("text") or "").strip()[:500]):
                    last_heard[0] = time.monotonic()
                    await session.send_realtime_input(text=q)

        checks: list[asyncio.Task[None]] = []

        async def report_turn(said: str) -> None:
            """The figures of one answer, after it is spoken (the voice never waits for this)."""
            figures, bad = await turn_figures(said, lang, ctx)
            stats["figures"] += len(figures)
            stats["unverified"] += len(bad)
            if bad:
                log.warning("call: the agent said numbers that are not in the report: %s", bad[:5])
            await caller.send_json(
                {
                    "type": "turn",
                    "said": said,
                    "figures": [{k: f.get(k) for k in ("id", "label", "value", "unit", "node")} for f in figures],
                    "unverified": bad,
                }
            )

        async def downlink() -> None:
            said = ""
            while True:
                got = False
                async for m in session.receive():
                    got = True
                    if m.tool_call:
                        responses = []
                        for fc in m.tool_call.function_calls or []:
                            resp, action = run_tool(fc.name or "", dict(fc.args or {}), ctx)
                            await caller.send_json({"type": "tool", "name": fc.name})
                            if action:
                                await caller.send_json(action)
                            responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=resp))
                        await session.send_tool_response(function_responses=responses)
                    if m.go_away is not None:
                        stats["ended"] = "server"
                        return
                    sc = m.server_content
                    if sc is None:
                        continue
                    if sc.interrupted:
                        await caller.send_json({"type": "interrupted"})
                    if sc.input_transcription and sc.input_transcription.text:
                        await caller.send_json({"type": "caption", "who": "caller", "text": sc.input_transcription.text})
                    if sc.output_transcription and sc.output_transcription.text:
                        said += sc.output_transcription.text
                        await caller.send_json({"type": "caption", "who": "agent", "text": sc.output_transcription.text})
                    if sc.model_turn:
                        for part in sc.model_turn.parts or []:
                            if part.inline_data and part.inline_data.data:
                                await caller.send_bytes(part.inline_data.data)
                    if sc.turn_complete or sc.interrupted:
                        if said:
                            stats["turns"] += 1
                            checks.append(asyncio.create_task(report_turn(said)))
                        said = ""
                if not got:  # the session closed
                    stats["ended"] = "server"
                    return

        async def watchdog() -> None:
            while True:
                await asyncio.sleep(1.0)
                if time.monotonic() - t0 >= cfg.call_max_seconds:
                    stats["ended"] = "time_limit"
                    return
                if time.monotonic() - last_heard[0] >= IDLE_S:
                    stats["ended"] = "idle"
                    return

        tasks = [asyncio.create_task(x()) for x in (uplink, downlink, watchdog)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for t in done:
                if not t.cancelled() and (exc := t.exception()):
                    raise exc
        finally:
            for t in tasks:
                t.cancel()
            if checks:  # let the last answer's figures reach the screen
                await asyncio.wait(checks, timeout=5)
    stats["seconds"] = round(time.monotonic() - t0, 1)
    stats["tools"] = ctx.tools_used
    log.info("call ended: %s", json.dumps({"project": ctx.project.id, "lang": lang, **stats}))
    if stats["ended"] != "hangup":
        try:
            await caller.send_json({"type": "ended", "reason": stats["ended"]})
        except Exception:  # noqa: S110 - the caller may already be gone
            pass
    return stats
