"""Das berechnete Modell als Bild: Quader in Schrägansicht von vorne links oben.

Damit Claude Entwurf und Ergebnis vergleichen kann (Selbstkontrolle), ohne dass dafür ein 3D-Renderer nötig ist.
Gezeichnet wird mit dem Maleralgorithmus: hintere Quader zuerst, je Quader die drei sichtbaren Flächen.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

FARBEN = {"holz": (216, 194, 160), "ergaenzt": (194, 65, 12), "polster": (201, 206, 214)}
HELLIGKEIT = {"oben": 1.12, "vorne": 0.95, "seite": 0.78}  # Licht von oben, Seite im Schatten


def _vektoren(drehung: float, neigung: float):
    """Blickrichtung von vorne links oben auf die Szene (x rechts, y nach hinten, z nach oben)."""
    t, p = math.radians(drehung), math.radians(neigung)
    zur_kamera = (-math.sin(t) * math.cos(p), -math.cos(t) * math.cos(p), math.sin(p))
    vor = tuple(-v for v in zur_kamera)
    rechts = (vor[1], -vor[0], 0.0)  # vor × (0, 0, 1)
    laenge = math.hypot(*rechts)
    rechts = tuple(v / laenge for v in rechts)
    hoch = (rechts[1] * vor[2] - rechts[2] * vor[1], rechts[2] * vor[0] - rechts[0] * vor[2],
            rechts[0] * vor[1] - rechts[1] * vor[0])
    return rechts, hoch, vor


def _punkt(p, achsen) -> tuple[float, float, float]:
    rechts, hoch, vor = achsen
    return (sum(a * b for a, b in zip(p, rechts)), sum(a * b for a, b in zip(p, hoch)), sum(a * b for a, b in zip(p, vor)))


def _flaechen(mn, mx):
    """Die drei von vorne links oben sichtbaren Flächen eines Quaders als Eckpunkt-Listen."""
    x0, y0, z0 = mn
    x1, y1, z1 = mx
    return [
        ("seite", [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)]),  # links
        ("vorne", [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)]),
        ("oben", [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]),
    ]


def modellbild(modell: dict, breite: int = 768, hoehe: int = 576, drehung: float = 30, neigung: float = 22) -> Image.Image:
    """``modell`` wie ``views.praesentation.modell_3d``: teile (min, max, ergaenzt), polster (min, max)."""
    achsen = _vektoren(drehung, neigung)
    quader = [("ergaenzt" if t.get("ergaenzt") else "holz", t["min"], t["max"]) for t in modell.get("teile", [])]
    quader += [("polster", p["min"], p["max"]) for p in modell.get("polster", [])]
    bild = Image.new("RGB", (breite, hoehe), (238, 240, 242))
    if not quader:
        return bild

    # Maßstab: alles passt mit Rand ins Bild
    ecken = [_punkt((x, y, z), achsen) for _, mn, mx in quader
             for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    u0, u1 = min(e[0] for e in ecken), max(e[0] for e in ecken)
    v0, v1 = min(e[1] for e in ecken), max(e[1] for e in ecken)
    rand = 24
    m = min((breite - 2 * rand) / max(u1 - u0, 1), (hoehe - 2 * rand) / max(v1 - v0, 1))
    du = (breite - (u1 - u0) * m) / 2
    dv = (hoehe - (v1 - v0) * m) / 2

    def bildpunkt(p):
        u, v, _ = _punkt(p, achsen)
        return ((u - u0) * m + du, hoehe - ((v - v0) * m + dv))

    stift = ImageDraw.Draw(bild)
    # Boden als Bezug
    x0, y0 = min(q[1][0] for q in quader), min(q[1][1] for q in quader)
    x1, y1 = max(q[2][0] for q in quader), max(q[2][1] for q in quader)
    stift.polygon([bildpunkt(p) for p in [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]], fill=(222, 225, 229))

    def tiefe(q):  # Mittelpunkt entlang der Blickrichtung; weiter hinten zuerst zeichnen
        _, mn, mx = q
        return _punkt(tuple((a + b) / 2 for a, b in zip(mn, mx)), achsen)[2]

    for art, mn, mx in sorted(quader, key=tiefe, reverse=True):
        for seite, punkte in _flaechen(mn, mx):
            farbe = tuple(min(255, round(c * HELLIGKEIT[seite])) for c in FARBEN[art])
            stift.polygon([bildpunkt(p) for p in punkte], fill=farbe, outline=(90, 80, 64))
    return bild
