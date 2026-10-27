"""Pull DEXA numbers from a report file. Prefer text; use an LLM only when a key is set."""

import json
import os
import re
from typing import Any


def extract_from_text(text: str) -> dict[str, Any]:
    blob = " ".join((text or "").split())
    bf = _first_float(
        blob,
        (
            r"(?:body\s*fat|fat\s*mass\s*%|bf\s*%)[^0-9]{0,24}(\d{1,2}(?:\.\d+)?)\s*%",
            r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:body\s*fat|fat)",
        ),
    )
    ffm = _first_float(
        blob,
        (
            r"(?:fat[-\s]*free\s*mass|lean\s*(?:mass|tissue)|ffm)[^0-9]{0,24}(\d{2,3}(?:\.\d+)?)\s*kg",
            r"(\d{2,3}(?:\.\d+)?)\s*kg\s*(?:fat[-\s]*free|lean|ffm)",
        ),
    )
    rmr = _first_float(
        blob,
        (
            r"(?:rmr|bmr|resting\s*(?:metabolic\s*)?rate|ree)[^0-9]{0,24}(\d{3,4})\s*k?cal",
            r"(\d{3,4})\s*k?cal(?:ories)?\s*(?:rmr|bmr|resting)",
        ),
    )
    measured = _first_date(blob)
    return {
        "dexa_bf_percent": _clamp(bf, 3, 60),
        "dexa_ffm_kg": _clamp(ffm, 20, 120),
        "dexa_rmr_kcal": int(_clamp(rmr, 900, 3500)) if rmr is not None else None,
        "dexa_measured_on": measured,
        "source": "text",
    }


def extract_from_bytes(data: bytes, content_type: str = "", name: str = "") -> dict[str, Any]:
    text = _pdf_text(data) if _looks_pdf(data, content_type, name) else ""
    parsed = extract_from_text(text) if text else {
        "dexa_bf_percent": None,
        "dexa_ffm_kg": None,
        "dexa_rmr_kcal": None,
        "dexa_measured_on": None,
        "source": "none",
    }
    llm = _llm_extract(data, content_type, name, text)
    if llm:
        for key in ("dexa_bf_percent", "dexa_ffm_kg", "dexa_rmr_kcal", "dexa_measured_on"):
            if llm.get(key) is not None and parsed.get(key) is None:
                parsed[key] = llm[key]
        parsed["source"] = "llm" if parsed["source"] == "none" else "text+llm"
    parsed["extracted_text"] = (text or "")[:4000]
    return parsed


def _looks_pdf(data: bytes, content_type: str, name: str) -> bool:
    if data[:4] == b"%PDF":
        return True
    return "pdf" in (content_type or "").lower() or (name or "").lower().endswith(".pdf")


def _pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        from io import BytesIO

        reader = PdfReader(BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


def openai_api_key():
    """The signed-in user's key from Settings → AI. No shared app secret."""
    try:
        from craftify_library.CraftifyAI import user_openai_key

        return user_openai_key()
    except Exception:
        return ""


def _llm_extract(data: bytes, content_type: str, name: str, text: str) -> dict[str, Any] | None:
    key = openai_api_key()
    if not key:
        return None
    prompt = (
        "Extract DEXA scan metrics as JSON with keys dexa_bf_percent, dexa_ffm_kg, "
        "dexa_rmr_kcal, dexa_measured_on (YYYY-MM-DD). Use null when missing.\n\n"
        + (text[:6000] if text else "The file is an image or an unreadable PDF. Infer only if obvious.")
    )
    try:
        return _openai_json(prompt, key)
    except Exception:
        return None


def _openai_json(prompt: str, key: str) -> dict[str, Any] | None:
    import json as _json
    import urllib.request

    body = {
        "model": os.environ.get("OPENAI_DEXA_MODEL") or "gpt-4o-mini",
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": prompt}],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=_json.dumps(body).encode(),
        headers={
            "Authorization": "Bearer %s" % key,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=40) as resp:
        payload = _json.loads(resp.read().decode())
    raw = payload["choices"][0]["message"]["content"]
    parsed = json.loads(raw)
    return {
        "dexa_bf_percent": _clamp(parsed.get("dexa_bf_percent"), 3, 60),
        "dexa_ffm_kg": _clamp(parsed.get("dexa_ffm_kg"), 20, 120),
        "dexa_rmr_kcal": int(_clamp(parsed.get("dexa_rmr_kcal"), 900, 3500)) if parsed.get("dexa_rmr_kcal") else None,
        "dexa_measured_on": parsed.get("dexa_measured_on"),
    }


def _first_float(text: str, patterns: tuple[str, ...]):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None


def _first_date(text: str):
    match = re.search(r"(20\d{2})[-/](\d{1,2})[-/](\d{1,2})", text)
    if not match:
        return None
    return "%s-%02d-%02d" % (match.group(1), int(match.group(2)), int(match.group(3)))


def _clamp(value, low, high):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number < low or number > high:
        return None
    return number
