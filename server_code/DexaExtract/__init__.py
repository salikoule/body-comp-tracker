"""Pull DEXA numbers from a report file. The user's OpenAI key reads the file itself; text regex is the fallback."""

import base64
import json
import os
import re
from typing import Any

REQUIRED = ("dexa_measured_on", "dexa_bf_percent", "dexa_ffm_kg", "dexa_rmr_kcal")
EXTRA_METRICS = ("total_mass_kg", "fat_mass_kg", "lean_mass_kg", "bmc_kg", "vat_g")
LIMITS = {
    "dexa_bf_percent": (3, 60),
    "dexa_ffm_kg": (20, 120),
    "dexa_rmr_kcal": (900, 3500),
    "total_mass_kg": (30, 250),
    "fat_mass_kg": (2, 120),
    "lean_mass_kg": (20, 120),
    "bmc_kg": (1, 6),
    "vat_g": (0, 5000),
}
PROMPT = (
    "You read DEXA body-composition reports. Return one JSON object with these keys, using numbers only "
    "(no units) and null when the report does not state the value:\n"
    "dexa_measured_on: scan date as YYYY-MM-DD\n"
    "dexa_bf_percent: total body fat percent\n"
    "dexa_ffm_kg: total fat-free mass in kg (lean tissue plus bone mineral content)\n"
    "dexa_rmr_kcal: resting metabolic rate in kcal/day\n"
    "total_mass_kg: total body mass in kg\n"
    "fat_mass_kg: total fat mass in kg\n"
    "lean_mass_kg: total lean tissue mass in kg, without bone\n"
    "bmc_kg: total bone mineral content in kg\n"
    "vat_g: visceral adipose tissue mass in grams\n"
    "Rules:\n"
    "- Use the whole-body total row (Total, Whole Body, Σύνολο, Ολόσωμη), never an arm, leg, trunk, android or gynoid row.\n"
    "- Reports are often European: a comma is the decimal mark ('28,8 %' is 28.8) and a dot groups thousands "
    "('22.055 g' is 22055 grams, so 22.055 kg). Convert grams to kg for every *_kg key.\n"
    "- Greek labels: Ιστός (%Λίπος) is body fat percent; Λίπος is fat mass; Ιστός χωρίς λίπος is lean mass; "
    "Οστική μάζα (BMC) is bone mineral content; Συνολική is total mass; Fat Free Mass is fat-free mass; "
    "Μετρηθείσα is the scan date (DD/MM/YYYY).\n"
    "- Body fat percent is a percentage near fat mass / total mass. Never put a mass value in dexa_bf_percent.\n"
    "- Copy numbers exactly as printed. Do not estimate."
)
MAX_STRIPS = 24
CONSISTENCY_PP = 1.5
CONSISTENCY_KG = 1.5


class DexaReadError(Exception):
    pass


def empty_result(source="none"):
    result = dict((key, None) for key in REQUIRED + EXTRA_METRICS)
    result["source"] = source
    return result


def extract_from_text(text: str) -> dict[str, Any]:
    blob = " ".join((text or "").split())
    result = empty_result("text")
    result["dexa_bf_percent"] = _clamp_key("dexa_bf_percent", _first_float(blob, (
        r"(?:body\s*fat|fat\s*mass\s*%|bf\s*%)[^0-9]{0,24}(\d{1,2}(?:\.\d+)?)\s*%",
        r"(\d{1,2}(?:\.\d+)?)\s*%\s*(?:body\s*fat|fat)",
    )))
    result["dexa_ffm_kg"] = _clamp_key("dexa_ffm_kg", _first_float(blob, (
        r"(?:fat[-\s]*free\s*mass|lean\s*(?:mass|tissue)|ffm)[^0-9]{0,24}(\d{2,3}(?:\.\d+)?)\s*kg",
        r"(\d{2,3}(?:\.\d+)?)\s*kg\s*(?:fat[-\s]*free|lean|ffm)",
    )))
    rmr = _clamp_key("dexa_rmr_kcal", _first_float(blob, (
        r"(?:rmr|bmr|resting\s*(?:metabolic\s*)?rate|ree)[^0-9]{0,24}(\d{3,4})\s*k?cal",
        r"(\d{3,4})\s*k?cal(?:ories)?\s*(?:rmr|bmr|resting)",
    )))
    result["dexa_rmr_kcal"] = int(rmr) if rmr is not None else None
    result["dexa_measured_on"] = _first_date(blob)
    return result


def extract_from_bytes(data: bytes, content_type: str = "", name: str = "", key: str | None = None,
                       strips=None) -> dict[str, Any]:
    """Read every metric we can. Raises DexaReadError with a user-facing reason when nothing could be read."""
    key = openai_api_key() if key is None else key
    is_pdf = _looks_pdf(data, content_type, name)
    if key:
        parts = _strip_parts(strips) or [_file_part(data, content_type, name, is_pdf)]
        result = normalize(_openai_read(parts, key))
        result["source"] = "ai"
        return result
    text = _pdf_text(data) if is_pdf else ""
    if not text:
        raise DexaReadError(
            "Add your OpenAI key in Settings → AI so the scan can be read automatically, or type the numbers below."
        )
    return extract_from_text(text)


def missing_required(values: dict[str, Any]) -> list[str]:
    return [key for key in REQUIRED if values.get(key) in (None, "")]


def normalize(raw: dict[str, Any]) -> dict[str, Any]:
    result = empty_result(raw.get("source") or "ai")
    for key in LIMITS:
        result[key] = _clamp_key(key, raw.get(key))
    if result["dexa_rmr_kcal"] is not None:
        result["dexa_rmr_kcal"] = int(round(result["dexa_rmr_kcal"]))
    if result["vat_g"] is not None:
        result["vat_g"] = int(round(result["vat_g"]))
    total, fat, lean, bmc = (result[key] for key in ("total_mass_kg", "fat_mass_kg", "lean_mass_kg", "bmc_kg"))
    if total and fat is not None and fat < total:
        derived_ffm = round(total - fat, 1)
        if lean is not None and bmc is not None and abs(lean + bmc - derived_ffm) > CONSISTENCY_KG:
            derived_ffm = None
        tissue = fat + lean if lean is not None else (total - bmc if bmc is not None else None)
        derived_bf = round(fat / tissue * 100, 1) if derived_ffm is not None and tissue else None
        if derived_bf is not None and (
            result["dexa_bf_percent"] is None or abs(result["dexa_bf_percent"] - derived_bf) > CONSISTENCY_PP
        ):
            result["dexa_bf_percent"] = derived_bf
        if derived_ffm is not None and (
            result["dexa_ffm_kg"] is None or abs(result["dexa_ffm_kg"] - derived_ffm) > CONSISTENCY_KG
        ):
            result["dexa_ffm_kg"] = derived_ffm
    if result["dexa_ffm_kg"] is None and lean is not None and bmc is not None:
        result["dexa_ffm_kg"] = round(lean + bmc, 1)
    result["dexa_measured_on"] = _iso_date(raw.get("dexa_measured_on"))
    return result


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


def _file_part(data: bytes, content_type: str, name: str, is_pdf: bool) -> dict[str, Any]:
    encoded = base64.b64encode(data).decode()
    if is_pdf:
        return {"type": "file", "file": {"filename": name or "dexa.pdf", "file_data": "data:application/pdf;base64," + encoded}}
    mime = content_type if (content_type or "").startswith("image/") else "image/jpeg"
    return {"type": "image_url", "image_url": {"url": "data:%s;base64,%s" % (mime, encoded)}}


def _strip_parts(strips) -> list[dict[str, Any]]:
    parts = []
    for strip in (strips or [])[:MAX_STRIPS]:
        if isinstance(strip, str) and strip.startswith("data:image/jpeg;base64,"):
            parts.append({"type": "image_url", "image_url": {"url": strip, "detail": "high"}})
    return parts


def _openai_read(parts: list[dict[str, Any]], key: str) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    intro = "Read this DEXA report."
    if parts and parts[0]["type"] == "image_url":
        intro = "Read this DEXA report. The images are overlapping horizontal strips of photographed pages, top to bottom."
    body = {
        "model": os.environ.get("OPENAI_DEXA_MODEL") or "gpt-4.1",
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": [{"type": "text", "text": intro}] + parts},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": "Bearer %s" % key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        raise DexaReadError(_http_reason(err)) from err
    except Exception as err:
        raise DexaReadError("The scan could not be read in time. Try again, or type the numbers below.") from err
    try:
        return json.loads(payload["choices"][0]["message"]["content"])
    except (KeyError, IndexError, ValueError) as err:
        raise DexaReadError("The AI reply was not readable. Try again, or type the numbers below.") from err


def _http_reason(err) -> str:
    if err.code == 401:
        return "OpenAI rejected the key in Settings → AI. Check it, or type the numbers below."
    if err.code == 429:
        return "OpenAI is rate limiting this key or it has no credit left. Try again later, or type the numbers below."
    try:
        detail = json.loads(err.read().decode()).get("error", {}).get("message") or ""
    except Exception:
        detail = ""
    return ("OpenAI could not read the file (%s). Type the numbers below." % detail[:160]) if detail else (
        "OpenAI could not read the file. Type the numbers below.")


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


def _iso_date(value):
    if not value:
        return None
    iso = _first_date(str(value))
    if iso:
        return iso
    match = re.search(r"(\d{1,2})[./-](\d{1,2})[./-](20\d{2})", str(value))
    if not match:
        return None
    return "%s-%02d-%02d" % (match.group(3), int(match.group(2)), int(match.group(1)))


def _clamp_key(key, value):
    low, high = LIMITS[key]
    return _clamp(value, low, high)


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
