"""AI document intake — classify an uploaded tax document and extract its key
fields with Claude. A single structured-output call per document; no tools.

Configuration (see config.py):
- ANTHROPIC_API_KEY — when unset, AI analysis is disabled and analyze_document
  raises AINotConfigured. Nothing else in the app depends on the key.
- ANTHROPIC_MODEL — defaults to claude-opus-5. Set a cheaper model
  (e.g. claude-haiku-4-5) for high-volume, cost-sensitive classification.
"""
import base64
import json
import os

from flask import current_app

# Swiss private-client tax documents the model should recognise. Free-form is
# allowed (the model may return another label) but these anchor its vocabulary.
KNOWN_DOC_TYPES = [
    "Lohnausweis", "Säule-3a-Bescheinigung", "Säule-2-/Pensionskassenausweis",
    "Bankkontoauszug", "Wertschriftenverzeichnis / Depotauszug",
    "Krankenkassen-Prämienabrechnung", "Zinsbescheinigung",
    "Hypothekarzinsausweis", "Liegenschaftsunterhalt / Rechnung",
    "Spendenbescheinigung", "Aus-/Weiterbildungskosten", "Kinderbetreuungskosten",
    "Steuererklärung Vorjahr", "Sonstiges",
]

_MEDIA_TYPES = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_type": {
            "type": "string",
            "description": "Dokumenttyp, bevorzugt einer der bekannten Typen.",
        },
        "summary": {
            "type": "string",
            "description": "Ein knapper deutscher Satz, was das Dokument enthält.",
        },
        "confidence": {"type": "string", "enum": ["hoch", "mittel", "niedrig"]},
        "fields": {
            "type": "array",
            "description": "Die wichtigsten extrahierten Felder.",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "value": {"type": "string"},
                },
                "required": ["label", "value"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["doc_type", "summary", "confidence", "fields"],
    "additionalProperties": False,
}


class AINotConfigured(RuntimeError):
    """Raised when ANTHROPIC_API_KEY is not set."""


class AIAnalysisError(RuntimeError):
    """Raised when the analysis call fails or returns nothing usable."""


def is_configured():
    return bool(current_app.config.get("ANTHROPIC_API_KEY"))


def _content_block(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    media_type = _MEDIA_TYPES.get(ext)
    if media_type is None:
        raise AIAnalysisError(f"Nicht unterstützter Dateityp: {ext or 'unbekannt'}")
    with open(file_path, "rb") as f:
        data = base64.standard_b64encode(f.read()).decode("utf-8")
    if media_type == "application/pdf":
        return {"type": "document",
                "source": {"type": "base64", "media_type": media_type, "data": data}}
    return {"type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data}}


def analyze_document(file_path, document_name=None):
    """Classify and extract fields from a document. Returns a dict with keys
    doc_type, summary, confidence, fields (list of {label, value}), model."""
    api_key = current_app.config.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise AINotConfigured("ANTHROPIC_API_KEY ist nicht gesetzt.")
    if not os.path.isfile(file_path):
        raise AIAnalysisError("Datei nicht gefunden.")

    import anthropic  # imported lazily so the app boots without the package

    model = current_app.config.get("ANTHROPIC_MODEL", "claude-opus-5")
    client = anthropic.Anthropic(api_key=api_key)

    prompt = (
        "Du bist Assistent eines Schweizer Treuhandbüros. Analysiere das "
        "beigefügte Steuerdokument einer Privatperson. Bestimme den Dokumenttyp "
        f"(bevorzugt einer von: {', '.join(KNOWN_DOC_TYPES)}), fasse den Inhalt "
        "in einem kurzen deutschen Satz zusammen und extrahiere die für die "
        "Steuererklärung wichtigsten Felder (Beträge mit Währung, Zeiträume, "
        "Namen, Kontonummern). Wenn du dir unsicher bist, wähle 'Sonstiges' und "
        "confidence 'niedrig'."
    )
    if document_name:
        prompt += f"\n\nDateiname: {document_name}"

    try:
        response = client.messages.create(
            model=model,
            max_tokens=2048,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": [_content_block(file_path),
                                                   {"type": "text", "text": prompt}]}],
        )
    except Exception as e:  # network / auth / API errors
        current_app.logger.warning("AI analysis failed: %s", e)
        raise AIAnalysisError("Die KI-Analyse ist fehlgeschlagen.") from e

    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), None)
    if not text:
        raise AIAnalysisError("Die KI-Analyse lieferte keine Daten.")
    try:
        data = json.loads(text)
    except (ValueError, TypeError) as e:
        raise AIAnalysisError("Die KI-Antwort konnte nicht gelesen werden.") from e

    data["model"] = getattr(response, "model", model)
    return data
