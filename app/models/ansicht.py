"""Das berechnete Modell als Bild: Quader in Schrägansicht von vorne links oben.

Damit Claude Entwurf und Ergebnis vergleichen kann (Selbstkontrolle), ohne dass dafür ein 3D-Renderer nötig ist.
Gezeichnet wird mit dem Maleralgorithmus: hintere Quader zuerst, je Quader die drei sichtbaren Flächen.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFont

FARBEN = {"holz": (216, 194, 160), "ergaenzt": (194, 65, 12), "polster": (201, 206, 214), "gurt": (59, 63, 70),
          "neu": (236, 128, 36), "blass": (236, 229, 218)}
KANTE = {"blass": (190, 182, 170)}
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


def _art(t: dict) -> str:
    return t.get("stil") or ("gurt" if t.get("gurt") else "ergaenzt" if t.get("ergaenzt") else "holz")


def modellbild(modell: dict, breite: int = 768, hoehe: int = 576, drehung: float = 30, neigung: float = 22,
               rahmen: dict | None = None, beschriften: str | None = None, hintergrund=(238, 240, 242),
               schrauben: list[dict] | None = None) -> Image.Image:
    """``modell`` wie ``views.praesentation.modell_3d``: teile (min, max, ergaenzt), polster (min, max).

    Für die Bauanleitung: ``teile[i]["stil"]`` = "neu" (hervorgehoben) oder "blass" (steht schon); ``rahmen`` = das
    ganze Modell, damit alle Schrittbilder denselben Ausschnitt haben; ``beschriften`` = "alle" oder "neu": Buchstaben
    (``teile[i]["b"]``) einmal je Buchstabe ins Bild schreiben.
    """
    achsen = _vektoren(drehung, neigung)
    quader = [(_art(t), t["min"], t["max"]) for t in modell.get("teile", [])]
    quader += [("polster", p["min"], p["max"]) for p in modell.get("polster", [])]
    bild = Image.new("RGB", (breite, hoehe), hintergrund)
    bezug = [(t["min"], t["max"]) for t in (rahmen or modell).get("teile", [])] or [(q[1], q[2]) for q in quader]
    if not quader or not bezug:
        return bild

    # Maßstab: alles passt mit Rand ins Bild
    ecken = [_punkt((x, y, z), achsen) for mn, mx in bezug
             for x in (mn[0], mx[0]) for y in (mn[1], mx[1]) for z in (mn[2], mx[2])]
    u0, u1 = min(e[0] for e in ecken), max(e[0] for e in ecken)
    v0, v1 = min(e[1] for e in ecken), max(e[1] for e in ecken)
    rand = max(24, breite // 20)
    m = min((breite - 2 * rand) / max(u1 - u0, 1), (hoehe - 2 * rand) / max(v1 - v0, 1))
    du = (breite - (u1 - u0) * m) / 2
    dv = (hoehe - (v1 - v0) * m) / 2

    def bildpunkt(p):
        u, v, _ = _punkt(p, achsen)
        return ((u - u0) * m + du, hoehe - ((v - v0) * m + dv))

    stift = ImageDraw.Draw(bild)
    # Boden als Bezug
    x0, y0 = min(q[0][0] for q in bezug), min(q[0][1] for q in bezug)
    x1, y1 = max(q[1][0] for q in bezug), max(q[1][1] for q in bezug)
    stift.polygon([bildpunkt(p) for p in [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)]], fill=(222, 225, 229))

    def tiefe(q):  # Mittelpunkt entlang der Blickrichtung; weiter hinten zuerst zeichnen
        _, mn, mx = q
        return _punkt(tuple((a + b) / 2 for a, b in zip(mn, mx)), achsen)[2]

    for art, mn, mx in sorted(quader, key=tiefe, reverse=True):
        for seite, punkte in _flaechen(mn, mx):
            farbe = tuple(min(255, round(c * HELLIGKEIT[seite])) for c in FARBEN[art])
            stift.polygon([bildpunkt(p) for p in punkte], fill=farbe, outline=KANTE.get(art, (90, 80, 64)))
    if schrauben:
        _schrauben(stift, schrauben, bildpunkt, achsen, breite)
    if beschriften:
        _buchstaben(stift, modell, bildpunkt, beschriften, breite)
    return bild


def _schrauben(stift: ImageDraw.ImageDraw, stellen: list[dict], bildpunkt, achsen, breite: int) -> None:
    """Schraubstellen als Punkte, nur auf Flächen, die zur Kamera zeigen (sonst sieht man sie im Bild nicht)."""
    _, _, vor = achsen
    r = max(5, breite // 110)
    for s in stellen:
        normale = [-v for v in s["r"]]  # die Schraube geht hinein, die Fläche zeigt hinaus
        if sum(n * v for n, v in zip(normale, vor)) >= -0.05:
            continue  # Fläche zeigt von der Kamera weg
        u, v = bildpunkt(s["p"])
        stift.ellipse([u - r, v - r, u + r, v + r], fill=(20, 24, 30), outline=(255, 255, 255), width=max(1, r // 3))


def _buchstaben(stift: ImageDraw.ImageDraw, modell: dict, bildpunkt, welche: str, breite: int) -> None:
    """Je Buchstabe ein Kreis mit dem Buchstaben, auf dem größten sichtbaren Teil dieser Art."""
    r = max(11, breite // 38)
    try:
        schrift = ImageFont.load_default(size=round(r * 1.25))
    except TypeError:  # sehr altes Pillow
        schrift = ImageFont.load_default()
    beste: dict[str, dict] = {}
    for t in modell.get("teile", []):
        b = t.get("b")
        if not b or (welche == "neu" and t.get("stil") != "neu"):
            continue
        groesse = sum(t["max"][a] - t["min"][a] for a in (0, 1, 2))
        if b not in beste or groesse > beste[b]["g"]:
            beste[b] = {"g": groesse, "t": t}
    gesetzt: list[tuple[float, float]] = []
    for b, x in sorted(beste.items()):
        t = x["t"]
        mitte = ((t["min"][0] + t["max"][0]) / 2, (t["min"][1] + t["max"][1]) / 2, t["max"][2])
        u, v = bildpunkt(mitte)
        for du, dv in gesetzt:  # nicht übereinander
            if abs(u - du) < 2.2 * r and abs(v - dv) < 2.2 * r:
                v -= 2.4 * r
        gesetzt.append((u, v))
        stift.ellipse([u - r, v - r, u + r, v + r], fill=(28, 37, 48), outline=(255, 255, 255), width=max(2, r // 6))
        stift.text((u, v), b, fill=(255, 255, 255), font=schrift, anchor="mm")
