from __future__ import annotations

import base64
import html
import re


def title_image_data_uri(title: str, labels: list[str]) -> str:
    """Create a lightweight SVG title card as an inline image for Blogger posts."""

    title_lines = [html.escape(line) for line in _wrap_title(title, 34).splitlines()]
    tspans = "".join(
        f'<tspan x="90" dy="{0 if index == 0 else 62}">{line}</tspan>' for index, line in enumerate(title_lines)
    )
    safe_label = html.escape(labels[0] if labels else "Latest Jobs")
    accent = _accent_for(labels)
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <rect width="1200" height="630" fill="#fff7ed"/>
  <rect x="44" y="44" width="1112" height="542" rx="24" fill="#ffffff" stroke="#b91c1c" stroke-width="8"/>
  <rect x="44" y="44" width="1112" height="116" rx="24" fill="#b91c1c"/>
  <rect x="44" y="122" width="1112" height="38" fill="#b91c1c"/>
  <text x="600" y="116" text-anchor="middle" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="54" font-weight="700" fill="#ffffff">TheDailyJob</text>
  <rect x="90" y="205" width="260" height="54" rx="12" fill="{accent}"/>
  <text x="220" y="241" text-anchor="middle" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="26" font-weight="700" fill="#ffffff">{safe_label}</text>
  <text x="90" y="315" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="52" font-weight="700" fill="#111827">{tspans}</text>
  <text x="90" y="520" font-family="Roboto, Arial, Helvetica, sans-serif" font-size="28" fill="#374151">Important Dates • Eligibility • Fee • Official Link</text>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def _wrap_title(title: str, width: int) -> str:
    words = re.sub(r"\s+", " ", title).strip().split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
        if len(lines) == 2:
            break
    if current and len(lines) < 3:
        lines.append(current)
    return "\n".join(lines[:3])


def _accent_for(labels: list[str]) -> str:
    palette = {
        "Admit Card": "#2563eb",
        "Results": "#16a34a",
        "Answer Key": "#7c3aed",
        "Syllabus": "#0891b2",
        "Railway Jobs": "#dc2626",
        "Bank Jobs": "#9333ea",
        "Defence Jobs": "#15803d",
    }
    for label in labels:
        if label in palette:
            return palette[label]
    return "#f97316"
