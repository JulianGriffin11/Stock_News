"""Render the weekly digest from structured copy + ranked rows."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.email.theme import ARCANE, FOOTER, HERO_IMAGE, MARKS_QUOTE

TEMPLATES = Path(__file__).resolve().parent / "templates"
STATIC = Path(__file__).resolve().parent / "static"


@dataclass(frozen=True)
class DigestListing:
    step: int
    title: str
    body: str
    url: str
    cta_label: str = "Read more \u2192"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(TEMPLATES),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def social_icon_path(filename: str) -> Path:
    path = STATIC / filename
    if not path.is_file():
        raise FileNotFoundError(f"missing footer icon {path}")
    return path


def _icon_src(filename: str, content_id: str, *, inline: bool) -> str:
    if not inline:
        return f"cid:{content_id}"
    raw = social_icon_path(filename).read_bytes()
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def footer_for_template(*, inline_icons: bool) -> dict:
    socials = []
    for social in FOOTER["socials"]:
        socials.append(
            {
                **social,
                "src": _icon_src(
                    social["filename"],
                    social["content_id"],
                    inline=inline_icons,
                ),
            }
        )
    return {**FOOTER, "socials": socials}


def footer_attachments() -> list[dict]:
    attachments: list[dict] = []
    for social in FOOTER["socials"]:
        raw = social_icon_path(social["filename"]).read_bytes()
        attachments.append(
            {
                "filename": social["filename"],
                "content": list(raw),
                "content_id": social["content_id"],
                "content_type": "image/png",
            }
        )
    return attachments


def render_digest(
    *,
    subject: str,
    reader_name: str,
    overview: list[str],
    listings: list[DigestListing],
    inline_icons: bool = False,
) -> tuple[str, str]:
    ctx = {
        "theme": ARCANE,
        "preview": subject,
        "reader_name": reader_name,
        "overview": overview,
        "listings": listings,
        "hero": HERO_IMAGE,
        "quote": MARKS_QUOTE,
        "footer": footer_for_template(inline_icons=inline_icons),
    }
    env = _env()
    html = env.get_template("digest.html").render(**ctx)
    text = env.get_template("digest.txt").render(**ctx)
    return html, text
