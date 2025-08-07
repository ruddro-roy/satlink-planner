from __future__ import annotations

from datetime import datetime
from typing import List
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from .models import PassSummary


def build_ics(norad_id: int, passes: List[PassSummary], title: str) -> str:
    # Very simple ICS builder
    def dtfmt(s: str) -> str:
        # s is ISO Z
        return s.replace("-", "").replace(":", "").replace("Z", "Z")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:-//satlink-planner//EN",
    ]
    for p in passes:
        lines += [
            "BEGIN:VEVENT",
            f"UID:{norad_id}-{p.aos_utc}",
            f"DTSTART:{dtfmt(p.aos_utc)}",
            f"DTEND:{dtfmt(p.los_utc)}",
            f"SUMMARY:{title} NORAD {norad_id} - Max Elev {p.max_elev_deg:.1f} deg",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def build_pdf(path: str, norad_id: int, passes: List[PassSummary], title: str) -> None:
    c = canvas.Canvas(path, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 16)
    c.drawString(1 * inch, height - 1 * inch, title)
    c.setFont("Helvetica", 12)
    c.drawString(1 * inch, height - 1.3 * inch, f"NORAD ID: {norad_id}")

    y = height - 1.8 * inch
    c.setFont("Helvetica-Bold", 12)
    c.drawString(1 * inch, y, "Passes:")
    y -= 0.2 * inch

    c.setFont("Helvetica", 10)
    for p in passes:
        if y < 1 * inch:
            c.showPage()
            y = height - 1 * inch
        c.drawString(1 * inch, y, f"AOS: {p.aos_utc}  LOS: {p.los_utc}  Max Elev: {p.max_elev_deg:.1f} deg")
        y -= 0.18 * inch

    c.showPage()
    c.save()
