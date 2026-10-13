"""X1 - vernacular voice gap-closing.

A shop-floor supervisor answers a gap question ("How many tonnes of scrap in August?") by voice
in Hindi, Punjabi, Tamil or English. ``gemini-3.5-transcribe`` transcribes Hindi/Punjabi/English
(smart mode, language codes, domain vocabulary); it does not list Tamil, so Tamil audio is
transcribed by Gemini 3.8 Flash's audio understanding. Gemini 3.8 Flash then reads the single
stated quantity from the transcript (reading spoken numerals, never computing). The value is
stored as evidence with the audio and transcript and must be confirmed by a person before it
counts as approved.
"""

from __future__ import annotations

from typing import Any

from app.agents.llm import LLMResult, gemini, text_part
from app.config import settings

LANG_CODES = {"hi": ["hi-IN"], "pa": ["pa-IN", "pa-Guru-IN"], "en": ["en-IN"]}
VOCAB = {
    "hi": ["टन", "किलो", "स्क्रैप", "कटिंग", "रॉड", "बोल्ट", "उत्पादन", "स्टेनलेस", "कार्बन"],
    "pa": ["ਟਨ", "ਕਿਲੋ", "ਸਕ੍ਰੈਪ", "ਰਾਡ", "ਬੋਲਟ", "ਸਟੇਨਲੈਸ"],
    "en": ["tonnes", "scrap", "wire rod", "stainless", "carbon steel", "bolts"],
}
FIELD_DESC = {
    "scrap_t": "tonnes of scrap / cut-offs",
    "produced_t": "tonnes of bolts produced",
    "rod_consumed_t": "tonnes of wire rod consumed",
}

READ_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "found": {"type": "boolean", "description": "true only if the speaker states one quantity for the asked item"},
        "value_text": {"type": "string", "description": "the quantity exactly as spoken, in the original script"},
        "value_num": {
            "type": "string",
            "description": "the same quantity as a plain decimal number ('.' separator); spoken fractions like saadhe/paune/sava converted to decimals",
        },
        "unit": {"type": "string", "description": "t or kg as spoken"},
        "quote": {"type": "string", "description": "the words of the transcript that contain the quantity"},
    },
    "required": ["found", "value_text", "value_num", "unit", "quote"],
}


def audio_part(data: bytes, mime: str) -> dict[str, Any]:
    import base64

    return {"type": "audio", "data": base64.b64encode(data).decode(), "mime_type": mime}


async def transcribe(audio: bytes, mime: str, lang: str) -> LLMResult:
    cfg = settings()
    if lang in LANG_CODES:
        return await gemini().transcribe(
            cfg.model_transcribe,
            audio_part(audio, mime),
            {"mode": {"type": "smart"}, "language_codes": LANG_CODES[lang], "custom_vocabulary": VOCAB[lang]},
        )
    # Tamil (not in gemini-3.5-transcribe's language list): Gemini 3.8 Flash audio understanding.
    # "The original script" alone came back in Kannada script for a Tamil note (live test,
    # 2026-10-13), so the language and its script are named, checked, and asked for once more.
    name, script = SCRIPTS.get(lang, ("the speaker's language", None))
    system = (
        "You transcribe short voice notes from an Indian factory floor. "
        f"The speaker speaks {name}. Output only the verbatim transcript, written in {name} script."
    )
    r = await gemini().text(
        cfg.model_flash, system, [text_part("Transcribe this voice note."), audio_part(audio, mime)], thinking_level="low"
    )
    if script and not in_script(r.data, script):
        r = await gemini().text(
            cfg.model_flash, system, [text_part(f"Transcribe this voice note in {name} script."), audio_part(audio, mime)]
        )
    return r


# Unicode block of each language transcribed by Flash (lower, upper code point).
SCRIPTS: dict[str, tuple[str, tuple[int, int] | None]] = {"ta": ("Tamil", (0x0B80, 0x0BFF))}


def in_script(text: str, block: tuple[int, int]) -> bool:
    """Most letters of the transcript are in the language's own script."""
    letters = [ch for ch in text or "" if ch.isalpha()]
    return bool(letters) and sum(block[0] <= ord(ch) <= block[1] for ch in letters) >= 0.6 * len(letters)


async def read_value(transcript: str, field_key: str, period: str | None, lang: str) -> LLMResult:
    what = FIELD_DESC.get(field_key, field_key)
    prompt = (
        f"Question asked to the supervisor: how many {what} in {period or 'the month'}?\n"
        f"Transcript ({lang}): {transcript}\n"
        "Return the one quantity the speaker states for that item. Do not add, subtract or estimate anything."
    )
    return await gemini().json(
        settings().model_flash,
        "You read one stated quantity from a factory voice note.",
        [text_part(prompt)],
        READ_SCHEMA,
        thinking_level="low",
    )
