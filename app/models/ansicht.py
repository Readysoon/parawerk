"""Das berechnete Modell als Bild: Quader in Schrägansicht von vorne links oben.

Damit Claude Entwurf und Ergebnis vergleichen kann (Selbstkontrolle), ohne dass dafür ein 3D-Renderer nötig ist.
Gezeichnet wird mit einem Tiefenpuffer: je Pixel gewinnt die Fläche, die der Kamera am nächsten ist.
"""
from __future__ import annotations

import math

import numpy as np
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

    # Verdeckung pixelgenau (Tiefenpuffer): der Maleralgorithmus irrt bei langen, dünnen Teilen nebeneinander
    teil, flaeche = _rastern(quader, bildpunkt, achsen, m, breite, hoehe)
    farben = np.array([[min(255, round(c * HELLIGKEIT[f])) for c in FARBEN[art]] for art, _, _ in quader
                       for f in ("seite", "vorne", "oben")], dtype=np.uint8).reshape(len(quader), 3, 3)
    kanten = np.array([KANTE.get(art, (90, 80, 64)) for art, _, _ in quader], dtype=np.uint8)
    pixel = np.array(bild)
    sichtbar = teil >= 0
    pixel[sichtbar] = farben[teil[sichtbar], flaeche[sichtbar]]
    # Kanten: wo Teil oder Fläche wechselt
    kennung = np.where(sichtbar, teil * 3 + flaeche, -1)
    rand_px = np.zeros_like(sichtbar)
    rand_px[:, 1:] |= kennung[:, 1:] != kennung[:, :-1]
    rand_px[1:, :] |= kennung[1:, :] != kennung[:-1, :]
    vorne_teil = np.maximum(teil, np.roll(teil, 1, axis=1))  # Kante in der Farbe des sichtbaren Teils
    vorne_teil = np.where(sichtbar, teil, vorne_teil)
    rand_px &= vorne_teil >= 0
    pixel[rand_px] = kanten[vorne_teil[rand_px]]
    bild = Image.fromarray(pixel)
    stift = ImageDraw.Draw(bild)
    if schrauben:
        _schrauben(stift, schrauben, bildpunkt, achsen, breite, teil, [t.get("id") for t in modell.get("teile", [])])
    if beschriften:
        _buchstaben(stift, modell, beschriften, breite, teil)
    return bild


def _rastern(quader, bildpunkt, achsen, massstab, breite, hoehe):
    """Je Pixel: welches Teil (Index) vorne liegt und welche seiner Flächen (0 Seite, 1 vorne, 2 oben)."""
    tiefe = np.full((hoehe, breite), np.inf)
    teil = np.full((hoehe, breite), -1, dtype=np.int32)
    flaeche = np.zeros((hoehe, breite), dtype=np.int8)
    for i, (_, mn, mx) in enumerate(quader):
        for f, (_, ecken) in enumerate(_flaechen(mn, mx)):
            p = [np.array(bildpunkt(e)) for e in ecken]
            d = [_punkt(e, achsen)[2] * massstab for e in ecken]
            e1, e2 = p[1] - p[0], p[3] - p[0]
            det = e1[0] * e2[1] - e1[1] * e2[0]
            if abs(det) < 1e-6:
                continue  # Fläche von der Kante gesehen
            us = [q[0] for q in p]
            vs = [q[1] for q in p]
            a0, a1 = max(0, int(math.floor(min(us)))), min(breite, int(math.ceil(max(us))) + 1)
            b0, b1 = max(0, int(math.floor(min(vs)))), min(hoehe, int(math.ceil(max(vs))) + 1)
            if a0 >= a1 or b0 >= b1:
                continue
            uu, vv = np.meshgrid(np.arange(a0, a1) + 0.5, np.arange(b0, b1) + 0.5)
            ru, rv = uu - p[0][0], vv - p[0][1]
            s_ = (ru * e2[1] - rv * e2[0]) / det
            t_ = (rv * e1[0] - ru * e1[1]) / det
            innen = (s_ >= -1e-3) & (s_ <= 1 + 1e-3) & (t_ >= -1e-3) & (t_ <= 1 + 1e-3)
            z = d[0] + s_ * (d[1] - d[0]) + t_ * (d[3] - d[0])
            ausschnitt = tiefe[b0:b1, a0:a1]
            neu = innen & (z < ausschnitt - 0.05)
            ausschnitt[neu] = z[neu]
            teil[b0:b1, a0:a1][neu] = i
            flaeche[b0:b1, a0:a1][neu] = f
    return teil, flaeche


def _schrauben(stift: ImageDraw.ImageDraw, stellen: list[dict], bildpunkt, achsen, breite: int, teil, ids) -> None:
    """Schraubstellen als Punkte, nur wo man sie sieht: Fläche zeigt zur Kamera und das Teil ist dort vorne."""
    _, _, vor = achsen
    r = max(5, breite // 110)
    h, w = teil.shape
    for s in stellen:
        normale = [-v for v in s["r"]]  # die Schraube geht hinein, die Fläche zeigt hinaus
        if sum(n * v for n, v in zip(normale, vor)) >= -0.05:
            continue  # Fläche zeigt von der Kamera weg
        u, v = bildpunkt(s["p"])
        if s.get("id") is not None:
            iu, iv = int(u), int(v)
            nah = teil[max(0, iv - 2):min(h, iv + 3), max(0, iu - 2):min(w, iu + 3)]
            if s["id"] not in ids or not (nah == ids.index(s["id"])).any():
                continue  # verdeckt
        stift.ellipse([u - r, v - r, u + r, v + r], fill=(20, 24, 30), outline=(255, 255, 255), width=max(1, r // 3))


def _buchstaben(stift: ImageDraw.ImageDraw, modell: dict, welche: str, breite: int, teil) -> None:
    """Je Buchstabe ein Kreis mit dem Buchstaben, mitten auf dem am besten sichtbaren Teil dieser Art."""
    r = max(11, breite // 38)
    try:
        schrift = ImageFont.load_default(size=round(r * 1.25))
    except TypeError:  # sehr altes Pillow
        schrift = ImageFont.load_default()
    anzahl = np.bincount(teil[teil >= 0].ravel(), minlength=len(modell.get("teile", [])) + 1)
    beste: dict[str, int] = {}
    for i, t in enumerate(modell.get("teile", [])):
        b = t.get("b")
        if not b or (welche == "neu" and t.get("stil") != "neu") or anzahl[i] < 2 * r * r:  # kaum zu sehen
            continue
        if b not in beste or anzahl[i] > anzahl[beste[b]]:
            beste[b] = i
    gesetzt: list[tuple[float, float]] = []
    for b, i in sorted(beste.items()):
        vv, uu = np.nonzero(teil == i)
        # Punkt im Teil, der am weitesten vom Rand weg ist (grob): Median, dann nächster Pixel des Teils
        mu, mv = float(np.median(uu)), float(np.median(vv))
        k = int(np.argmin((uu - mu) ** 2 + (vv - mv) ** 2))
        au, av = float(uu[k]), float(vv[k])
        u, v = au, av
        for du_, dv_ in [(0, 0), (0, -2.4), (2.4, 0), (-2.4, 0), (0, 2.4), (2.4, -2.4), (-2.4, -2.4), (0, -4.8)]:
            u, v = au + du_ * r, av + dv_ * r  # nicht übereinander: ausweichen, mit Strich zum Teil
            if not any(abs(u - du) < 2.2 * r and abs(v - dv) < 2.2 * r for du, dv in gesetzt):
                break
        gesetzt.append((u, v))
        if (u, v) != (au, av):
            stift.line([(au, av), (u, v)], fill=(28, 37, 48), width=max(2, r // 6))
            stift.ellipse([au - r / 4, av - r / 4, au + r / 4, av + r / 4], fill=(28, 37, 48))
        stift.ellipse([u - r, v - r, u + r, v + r], fill=(28, 37, 48), outline=(255, 255, 255), width=max(2, r // 6))
        stift.text((u, v), b, fill=(255, 255, 255), font=schrift, anchor="mm")
