"""German (Swiss) localization helpers for the UI.

Stored status values stay English (routes/migrations untouched); we translate at
render time via Jinja filters. Also provides Swiss date and CHF formatting.
"""

# Stored English status -> displayed German (Swiss usage).
STATUS_DE = {
    "Open": "Offen",
    "Quote requested": "Offerte angefragt",
    "Review Quote": "Offerte prüfen",
    "Quote accepted": "Offerte angenommen",
    "Quote rejected": "Offerte abgelehnt",
    "Quote withdrawn": "Anfrage zurückgezogen",
    "Documents uploaded": "Dokumente hochgeladen",
    "Documents approved": "Dokumente freigegeben",
    "Documents rejected": "Dokumente abgelehnt",
    "Documents Downloaded": "Dokumente heruntergeladen",
    "Additional Documents Downloaded": "Zusätzliche Dokumente heruntergeladen",
    "Additional documents requested": "Zusätzliche Unterlagen angefordert",
    "Additional documents uploaded": "Zusätzliche Unterlagen hochgeladen",
    "Draft tax return submitted": "Entwurf eingereicht",
    "Draft tax return approved": "Entwurf genehmigt",
    "Draft tax return rejected": "Entwurf abgelehnt",
    "Completed": "Abgeschlossen",
    # Quote enum
    "Pending": "Offen",
    "In Review": "In Prüfung",
    "Accepted": "Angenommen",
    "Rejected": "Abgelehnt",
    "Draft Tax Return in Review": "Entwurf in Prüfung",
    "Tax Return Approved": "Steuererklärung freigegeben",
}


def status_de(value):
    if value is None:
        return ""
    return STATUS_DE.get(str(value), str(value))


def date_ch(value):
    """Format a date/datetime as 31.03.2026."""
    if not value:
        return "—"
    try:
        return value.strftime("%d.%m.%Y")
    except AttributeError:
        return str(value)


def datetime_ch(value):
    if not value:
        return "—"
    try:
        return value.strftime("%d.%m.%Y %H:%M")
    except AttributeError:
        return str(value)


def chf(value):
    """8'420 — apostrophe thousands separator, no decimals for whole numbers."""
    if value is None or value == "":
        return "—"
    try:
        n = float(value)
    except (TypeError, ValueError):
        return str(value)
    whole = int(round(n))
    s = f"{whole:,}".replace(",", "'")
    return s


def chf_amount(value):
    """CHF 480 — inline currency."""
    if value is None or value == "":
        return "—"
    return f"CHF {chf(value)}"


def register_filters(app):
    app.jinja_env.filters["status_de"] = status_de
    app.jinja_env.filters["date_ch"] = date_ch
    app.jinja_env.filters["datetime_ch"] = datetime_ch
    app.jinja_env.filters["chf"] = chf
    app.jinja_env.filters["chf_amount"] = chf_amount
