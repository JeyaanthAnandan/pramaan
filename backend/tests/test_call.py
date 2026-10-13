"""Call Pramaan (app/agents/call.py, app/api/call.py): the tools, the numbers guard on speech and a
whole call over the WebSocket against a scripted Gemini Live session (CI never calls Gemini)."""

from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.genai import types

from app.agents import call
from app.demo import loader
from app.evidence.store import store


@pytest.fixture()
def ctx(mem_store: Any) -> call.CallContext:
    info = loader.restore_cached()
    assert info
    pid = info["project_id"]
    return call.CallContext.build(store().get_project(pid), store().get_latest_result(pid))  # type: ignore[arg-type]


def test_the_agent_gets_the_report_as_facts_and_speaks_the_callers_language(ctx: call.CallContext) -> None:
    s = call.system_instruction(ctx, "pa")
    assert "Speak Punjabi" in s and "verdict.secured" in s and "409,545" in s and "Never compute" in s
    cfg = call.live_config(ctx, "vi")
    assert cfg.speech_config and cfg.speech_config.language_code == "vi-VN"
    assert {f.name for t in cfg.tools or [] for f in t.function_declarations or []} == {  # type: ignore[union-attr]
        "explain_number",
        "open_evidence",
        "search_guidance",
        "open_items",
    }


def test_tools_answer_from_the_engine_and_the_guidance(ctx: call.CallContext) -> None:
    r, action = call.run_tool("explain_number", {"fact_id": "P1.see"}, ctx)
    assert action is None and r["figure"]["value"].startswith("2.04") and r["inputs"]
    r, action = call.run_tool("open_evidence", {"fact_id": "P1.see"}, ctx)
    assert r["shown"] and action == {"type": "action", "name": "open_evidence", "node": "P1.see", "label": r["figure"]}
    r, action = call.run_tool("open_evidence", {"fact_id": "verdict.secured"}, ctx)  # a sum: no proof page of its own
    assert not r["shown"] and action is None
    r, _ = call.run_tool("search_guidance", {"question": "is scrap counted"}, ctx)
    assert r["passages"] and {"doc", "page", "text"} <= set(r["passages"][0])
    r, _ = call.run_tool("open_items", {}, ctx)
    assert r["count"] >= 1
    assert "error" in call.run_tool("delete_everything", {}, ctx)[0]
    assert ctx.tools_used[:2] == ["explain_number", "open_evidence"]


def test_numbers_the_agent_says_are_checked_against_the_report(ctx: call.CallContext) -> None:
    # English transcript with the figures spelled out (live test, 2026-10-13)
    figs, bad = call.check_spoken(
        "Your data saves the buyer a total of four hundred nine thousand five hundred forty-five euros per year.", ctx
    )
    assert [f["value"] for f in figs] == ["409,545"] and not bad
    # Hindi: digits, Indian grouping and a Devanagari digit
    figs, bad = call.check_spoken("आपके खरीदार को हर साल 409,545 EUR यानी 4,43,93,192 INR की बचत होगी। SEE २.040 है।", ctx)
    assert {f["value"] for f in figs} >= {"409,545", "4,43,93,192"} and not bad
    # Punjabi wrote 409,545 in Indian grouping
    assert call.check_spoken("ਹਰ ਸਾਲ 4,09,545 EUR", ctx)[0]
    # a number that is not in the report is caught; years and small counts are not numbers to check
    figs, bad = call.check_spoken("In 2026 your buyer pays 12,345 EUR on 1 of 2 lines.", ctx)
    assert bad == ["12345"]


def test_numbers_rebuilt_from_words_add_cards_but_never_a_warning(monkeypatch: pytest.MonkeyPatch, ctx: call.CallContext) -> None:
    """Live Punjabi test: the transcript garbled the spoken words, the rewrite gave 409057."""
    sent: list[dict[str, Any]] = []

    class Ws:
        async def send_json(self, d: dict[str, Any]) -> None:
            sent.append(d)

    async def garbled(text: str, lang: str) -> str:
        return "ਹਰ ਸਾਲ 409057 ਯੂਰੋ, ਯਾਨੀ 4,43,93,192 INR"

    monkeypatch.setattr(call, "spoken_digits", garbled)
    figures, bad = call.check_spoken("ਚਾਰ ਲੱਖ ਨੌ ਹਜ਼ਾਰ ਪੰਜ ਸੌਤਾਲੀ ਯੂਰੋ", ctx)
    assert figures == [] and bad == []  # words in Gurmukhi: nothing to check deterministically
    out = asyncio.run(call.turn_figures("ਚਾਰ ਲੱਖ ਨੌ ਹਜ਼ਾਰ ਪੰਜ ਸੌਤਾਲੀ ਯੂਰੋ", "pa", ctx))
    assert [f["value"] for f in out[0]] == ["4,43,93,192"] and out[1] == []


def test_words_to_digits() -> None:
    w = call.words_to_digits
    assert w("eight point six nine three tonnes") == "8.693 tonnes"
    assert w("four crores forty-three lakhs ninety-three thousand one hundred ninety-two rupees") == "44393192 rupees"
    assert w("one hundred and twenty") == "120"
    assert w("a point of view") == "a point of view"


# ------------------------------------------------------------------ a whole call, scripted


def _msg(**kw: Any) -> types.LiveServerMessage:
    return types.LiveServerMessage(**kw)


def _say(text: str, done: bool = True) -> types.LiveServerMessage:
    audio = types.Content(
        role="model", parts=[types.Part(inline_data=types.Blob(data=b"\x01\x00" * 480, mime_type="audio/pcm;rate=24000"))]
    )
    return _msg(
        server_content=types.LiveServerContent(output_transcription=types.Transcription(text=text), model_turn=audio, turn_complete=done)
    )


class ScriptedSession:
    """Answers the greeting, then the first question: asks to open the lens, then says a figure."""

    def __init__(self) -> None:
        self.turns: asyncio.Queue[list[types.LiveServerMessage]] = asyncio.Queue()
        self.sent: list[Any] = []
        self.tool_responses: list[Any] = []
        self.asked = False

    async def send_realtime_input(self, **kw: Any) -> None:
        self.sent.append(kw)
        if "text" in kw and kw["text"].startswith("(The call has just started"):
            await self.turns.put([_say("Namaste, main Pramaan hoon.")])
        elif "audio" in kw and not self.asked:
            self.asked = True
            await self.turns.put(
                [
                    _msg(server_content=types.LiveServerContent(input_transcription=types.Transcription(text="मेरे खरीदार को कितनी बचत?"))),
                    _msg(
                        tool_call=types.LiveServerToolCall(
                            function_calls=[types.FunctionCall(id="c1", name="open_evidence", args={"fact_id": "P1.see"})]
                        )
                    ),
                ]
            )

    async def send_tool_response(self, function_responses: list[Any]) -> None:
        self.tool_responses += function_responses
        await self.turns.put([_say("Aapka data khareedaar ko har saal 409,545 EUR ", done=False), _say("aur 99,999 EUR bachata hai.")])

    async def receive(self) -> Any:
        for m in await self.turns.get():
            yield m


def _client(monkeypatch: pytest.MonkeyPatch, session: ScriptedSession) -> TestClient:
    from app.main import app

    @asynccontextmanager
    async def connect(_config: Any) -> Any:
        yield session

    async def digits(text: str, lang: str) -> str:  # the Flash-Lite rewrite, without Gemini
        return call.words_to_digits(text)

    monkeypatch.setattr(call, "connect", connect)
    monkeypatch.setattr(call, "spoken_digits", digits)
    monkeypatch.setenv("GEMINI_VERTEX_READY", "1")
    return TestClient(app)


def test_a_call_end_to_end_over_the_websocket(monkeypatch: pytest.MonkeyPatch, mem_store: Any) -> None:
    session = ScriptedSession()
    with _client(monkeypatch, session) as c:
        pid = c.post("/api/demo/load", json={}).json()["project_id"]
        with c.websocket_connect(f"/api/projects/{pid}/call?lang=hi") as ws:
            assert ws.receive_json()["type"] == "ready"
            events: list[Any] = []

            def until(kind: str) -> dict[str, Any]:
                while True:
                    m = ws.receive()
                    if m.get("bytes") is not None:
                        events.append(("audio", len(m["bytes"])))
                        continue
                    e = json.loads(m["text"])
                    events.append(e)
                    if e["type"] == kind:
                        return e

            assert until("turn")["figures"] == []  # the greeting has no figures
            ws.send_bytes(b"\x00\x00" * 1600)  # 100 ms of microphone
            action = until("action")
            assert action["node"] == "P1.see"
            turn = until("turn")
            assert [f["value"] for f in turn["figures"]] == ["409,545"] and turn["unverified"] == ["99999"]
            ws.send_text(json.dumps({"type": "hangup"}))
    assert ("audio", 960) in events
    assert {"type": "caption", "who": "caller", "text": "मेरे खरीदार को कितनी बचत?"} in events
    assert session.tool_responses[0].response["shown"] is True
    assert any("audio" in s and s["audio"].mime_type == "audio/pcm;rate=16000" for s in session.sent)


def test_a_call_needs_the_projects_passcode_and_a_report(monkeypatch: pytest.MonkeyPatch, mem_store: Any) -> None:
    with _client(monkeypatch, ScriptedSession()) as c:
        own = c.post("/api/projects", json={"name": "Mine", "company": "Mine Co (SAMPLE)"}).json()
        pid = own["id"]
        with c.websocket_connect(f"/api/projects/{pid}/call") as ws:  # this browser has the cookie, no report yet
            assert ws.receive_json() == {"type": "error", "code": "no_report"}
        c.cookies.clear()
        with c.websocket_connect(f"/api/projects/{pid}/call") as ws:
            assert ws.receive_json() == {"type": "error", "code": "private"}
        demo = c.post("/api/demo/load", json={}).json()["project_id"]
        with c.websocket_connect(f"/api/projects/{demo}/call", headers={"origin": "https://evil.example"}) as ws:
            assert ws.receive_json() == {"type": "error", "code": "origin"}
