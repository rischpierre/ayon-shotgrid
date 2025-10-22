from __future__ import annotations
import datetime
import hashlib
import urllib.parse

from whiteboard.models import Day, Week

def _hash_color(key: str) -> str:
    h = int(hashlib.sha256(key.encode('utf-8')).hexdigest()[:8], 16)
    hue = h % 360
    # Use HSL with fixed saturation/lightness and convert to hex-ish via hsl() in SVG
    return f"hsl({hue},70%,35%)"

def _svg_data_uri(svg: str) -> str:
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)

def solid_color_thumb(width: int, height: int, key: str) -> str:
    color = _hash_color(key)
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"><rect width="100%" height="100%" fill="{color}"/></svg>'
    return _svg_data_uri(svg)

def identicon_thumb(size: int, key: str) -> str:
    # Simple 5x5 mirrored identicon
    color = _hash_color(key)
    bg = "#0f1222"
    bits = int(hashlib.sha256(key.encode('utf-8')).hexdigest(), 16)
    idx = 0
    grid = []
    for _y in range(5):
        row = []
        for _x in range(3):  # mirror last two
            row.append(((bits >> idx) & 1) == 1)
            idx += 1
        grid.append(row + row[-2::-1])
    cell = size // 5
    rects = []
    for y in range(5):
        for x in range(5):
            if grid[y][x]:
                rects.append(f'<rect x="{x*cell}" y="{y*cell}" width="{cell}" height="{cell}" fill="{color}"/>')
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}"><rect width="100%" height="100%" fill="{bg}"/>' + ''.join(rects) + '</svg>'
    return _svg_data_uri(svg)

def _current_monday() -> datetime.date:
    today = datetime.date.today()
    return today - datetime.timedelta(days=today.weekday())  # Monday=0

def _date_from_week_day(week: Week, day: Day) -> datetime.date:
    monday = _current_monday()
    wk_idx = int(week[1])  # 'w0' -> 0
    day_idx_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4}
    return monday + datetime.timedelta(days=wk_idx * 7 + day_idx_map[day])
