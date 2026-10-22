"""DXF-Export (R12, nur LINE und TEXT): jedes Teil als Rechteck Länge × Breite nebeneinander."""
from __future__ import annotations

import re

from .engine.grundlagen import Bauteil, mm, zahl


def teile_als_dxf(members: list[Bauteil]) -> str:
    zeilen: list[str] = []

    def add(*werte) -> None:
        zeilen.extend(zahl(v) for v in werte)

    def linie(layer: str, x1, y1, x2, y2) -> None:
        add(0, "LINE", 8, layer, 10, x1, 20, y1, 30, 0, 11, x2, 21, y2, 31, 0)

    add(0, "SECTION", 2, "ENTITIES")
    x = 0
    for m in members:
        d = sorted((mm(m.max[a] - m.min[a]) for a in (0, 1, 2)), reverse=True)
        w, h = d[0], d[1]
        layer = re.sub(r"[^A-Za-z0-9]", "_", m.name or "TEIL").upper()
        linie(layer, x, 0, x + w, 0)
        linie(layer, x + w, 0, x + w, h)
        linie(layer, x + w, h, x, h)
        linie(layer, x, h, x, 0)
        add(0, "TEXT", 8, "BESCHRIFTUNG", 10, x + 5, 20, h / 2, 30, 0, 40, min(20, h / 3), 1, f"{m.name} {w}x{h}x{d[2]}")
        x += w + 40
    add(0, "ENDSEC", 0, "EOF")
    return "\n".join(zeilen)
