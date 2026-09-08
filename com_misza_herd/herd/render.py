"""72×72 key art: project is the hero, kind is the color, status is motion."""

from __future__ import annotations

import math
import os
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

SIZE = 144
KIND_COLORS = {
    "pi": (244, 114, 182),
    "claude": (224, 145, 90),
    "codex": (52, 211, 153),
    "gemini": (96, 165, 250),
    "cursor": (167, 139, 250),
    "devin": (251, 191, 36),
    "agy": (236, 72, 153),
    "cline": (45, 212, 191),
    "omp": (148, 163, 184),
    "mastracode": (251, 113, 133),
    "opencode": (59, 130, 246),
    "copilot": (192, 132, 252),
    "kimi": (253, 224, 71),
    "kiro": (251, 146, 60),
    "droid": (74, 222, 128),
    "amp": (232, 121, 249),
    "grok": (226, 232, 240),
    "hermes": (163, 230, 53),
    "kilo": (252, 165, 165),
    "qodercli": (125, 211, 252),
    "qwen": (129, 140, 248),
    "maki": (253, 164, 175),
}
STATUS_BAR = {
    "blocked": (220, 68, 68),
    "done": (232, 196, 64),
    "working": (90, 102, 118),
    "idle": (58, 62, 70),
}
FONTS = [
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/liberation/LiberationSans-Bold.ttf",
]


def breath(now: float) -> float:
    # Same period as Omaherd's working dots (~1.9s), wider swing so the
    # LCD actually reads as a pulse instead of a flicker.
    phase = (now % 1.9) / 1.9
    return 0.18 + 0.82 * (0.5 + 0.5 * math.cos(phase * 2 * math.pi))


def breath_step(now: float) -> int:
    return int(round(breath(now) * 10))


@lru_cache(maxsize=4)
def _font(size: int):
    for path in FONTS:
        if os.path.isfile(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _mix(a, b, t: float):
    t = max(0.0, min(1.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _kind_rgb(kind: str):
    return KIND_COLORS.get(kind, (226, 232, 240))


def _project_lines(name: str) -> list[str]:
    text = " ".join(str(name or "project").replace("_", " ").split())
    if len(text) <= 10:
        return [text]
    parts = text.split()
    if len(parts) >= 2:
        mid = max(1, len(parts) // 2)
        return [" ".join(parts[:mid])[:12], " ".join(parts[mid:])[:12]]
    return [text[:10], text[10:20]]


def _fit(draw: ImageDraw.ImageDraw, lines: list[str], max_width: int, start: int = 36) -> tuple:
    for size in range(start, 16, -2):
        font = _font(size)
        widths = [draw.textbbox((0, 0), line, font=font)[2] for line in lines]
        if max(widths) <= max_width:
            return font, size
    return _font(16), 16


def _luma(rgb) -> float:
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def _outlined(draw, xy, text, font, fill, outline, width=3):
    x, y = xy
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx or dy:
                draw.text((x + dx, y + dy), text, font=font, fill=outline)
    draw.text((x, y), text, font=font, fill=fill)


def render_empty() -> Image.Image:
    return Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 255))


def render_agent(workspace: str, kind: str, status: str, host: str, now: float) -> Image.Image:
    image = Image.new("RGBA", (SIZE, SIZE), (8, 9, 12, 255))
    draw = ImageDraw.Draw(image)
    rgb = _kind_rgb(kind)
    loud = status in ("blocked", "done")
    pulse = breath(now) if status in ("working", "blocked", "done") else 1.0
    if loud:
        pulse = 0.22 + 0.78 * pulse

    wash = {
        "blocked": _mix((40, 8, 8), (150, 24, 24), pulse),
        "done": _mix((36, 28, 6), (150, 120, 18), pulse),
        "working": _mix((12, 14, 18), (36, 42, 52), pulse),
        "idle": (10, 11, 14),
    }.get(status, (10, 11, 14))
    draw.rectangle((0, 0, SIZE, SIZE), fill=wash + (255,))

    bar = STATUS_BAR.get(status, STATUS_BAR["idle"])
    if status == "blocked":
        bar = _mix((140, 28, 28), (255, 88, 88), pulse)
    elif status == "done":
        bar = _mix((160, 130, 24), (255, 220, 80), pulse)
    elif status == "working":
        bar = _mix((50, 58, 70), (140, 150, 165), pulse)
    header = 40 if loud else 36 if status == "working" else 32
    draw.rectangle((0, 0, SIZE, header), fill=bar + (255,))
    if status in ("working", "blocked", "done"):
        glow = _mix(bar, (255, 255, 255), 0.28 * pulse)
        draw.rectangle((0, header, SIZE, header + 3), fill=glow + (255,))

    header_light = _luma(bar) >= 140
    header_ink = (12, 12, 14) if header_light else (255, 255, 255)
    header_halo = (255, 255, 255) if header_light else (0, 0, 0)
    bits = []
    if host and host != "local":
        bits.append(host.split(".")[0].upper())
    bits.append({"blocked": "WAIT", "done": "DONE", "working": "RUN", "idle": "IDLE"}.get(status, status.upper()))
    meta = " ".join(bits)
    meta_font = _font(22)
    box = draw.textbbox((0, 0), meta, font=meta_font)
    if box[2] - box[0] > SIZE - 8:
        meta_font = _font(18)
        box = draw.textbbox((0, 0), meta, font=meta_font)
    mx = (SIZE - (box[2] - box[0])) // 2
    my = max(2, (header - (box[3] - box[1])) // 2 - 2)
    _outlined(draw, (mx, my), meta, meta_font, header_ink + (255,), header_halo + (255,), 2)

    body_light = _luma(wash) >= 90
    ink = (12, 12, 14) if body_light else (255, 255, 255)
    halo = (255, 255, 255) if body_light else (0, 0, 0)
    if status == "idle":
        project_color = _mix(rgb, ink, 0.35)
    else:
        project_color = rgb
    if _luma(project_color) > 200 and not body_light:
        project_color = _mix(project_color, (255, 255, 255), 0.15)
    elif _luma(project_color) < 80 and body_light:
        project_color = _mix(project_color, (20, 20, 20), 0.45)

    lines = _project_lines(workspace)
    font, _ = _fit(draw, lines, SIZE - 14, start=34)
    line_h = font.size + 2
    block_h = line_h * len(lines)
    y = header + max(4, (SIZE - header - block_h) // 2)
    for line in lines:
        box = draw.textbbox((0, 0), line, font=font)
        x = (SIZE - (box[2] - box[0])) // 2
        _outlined(draw, (x, y), line, font, project_color + (255,), halo + (255,), 3)
        y += line_h
    return image
