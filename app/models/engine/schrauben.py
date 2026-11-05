"""Schrauben je Verbindung: welche (Durchmesser × Länge), wo (Stellen zum Anzeichnen) und von welcher Seite.

Faustregeln aus Holzbau und Baumarkt-Anleitungen:
- Durch das dünnere der beiden Teile in das dickere schrauben (von außen, Kopf versenkt).
- Länge mindestens 2 × die Dicke des durchgeschraubten Teils, aber nicht durch das andere Teil hindurch.
- Durchmesser: Rahmenholz an Rahmenholz 6 mm, sonst 4 mm (5 mm ab 60 mm Länge).
- Zwei Schrauben je Verbindung, versetzt (nicht in einer Faserlinie), Randabstand etwa 5 × Durchmesser.
"""
from __future__ import annotations

from .grundlagen import SLATS, Bauteil, ext, prio

JE_VERBINDUNG = 2
LAENGEN = {4: [30, 40, 50, 60, 70, 80], 5: [50, 60, 70, 80, 90, 100, 120], 6: [80, 100, 120, 140, 160, 180, 200]}
PREIS_JE_MM = {4: 0.0013, 5: 0.0019, 6: 0.0025}  # € je mm Länge und Stück, Großpackung (z. B. 6×100 ≈ 0,25 €)


def verbindung(j: dict) -> dict | None:
    """Schraube für eine Verbindung oder None (Latte an Latte, Gurte werden getackert)."""
    a, b, ax = j["a"], j["b"], j["ax"]
    if max(prio(a), prio(b)) < 4 or "gurt" in (a.typ, b.typ):
        return None
    durch, ins = (a, b) if ext(a, ax) <= ext(b, ax) else (b, a)
    if ins.rolle in SLATS and ax == ins.long:
        return None  # nicht ins Hirnholz einer Latte oder eines Bretts: die liegt auf und wird von oben geschraubt
    dicke, tiefe = ext(durch, ax), ext(ins, ax)
    d = 6 if a.typ == "kantholz" and b.typ == "kantholz" else 4
    passend = [l for l in LAENGEN[d] if l >= 2 * dicke and l <= dicke + tiefe - 5]
    if not passend and d == 4:
        d = 5
        passend = [l for l in LAENGEN[d] if l >= 2 * dicke and l <= dicke + tiefe - 5]
    if passend:
        laenge = passend[0]
    else:  # anderes Teil zu dünn für 2 × Dicke: so lang wie möglich, ohne durchzugehen
        moeglich = [l for l in LAENGEN[d] if l <= dicke + tiefe - 5] or [LAENGEN[d][0]]
        laenge = moeglich[-1]
    if d == 4 and laenge >= 60:
        d = 5
    return {"d": d, "l": laenge, "durch": durch, "ins": ins, "ax": ax, "stellen": _stellen(durch, ins, ax, d)}


def _stellen(durch: Bauteil, ins: Bauteil, ax: int, d: int) -> list[dict]:
    """Zwei Schraubstellen auf der Außenseite des durchgeschraubten Teils, versetzt, mit Randabstand."""
    andere = [a for a in (0, 1, 2) if a != ax]
    lo = {a: max(durch.min[a], ins.min[a]) for a in andere}
    hi = {a: min(durch.max[a], ins.max[a]) for a in andere}
    lang, kurz = sorted(andere, key=lambda a: -(hi[a] - lo[a]))
    rand = min(5 * d, (hi[lang] - lo[lang]) / 4)
    aussen_min = durch.min[ax] < ins.min[ax]  # durchgeschraubtes Teil liegt auf der kleineren Seite
    seite = durch.min[ax] if aussen_min else durch.max[ax]
    stellen = []
    for i, (fl, fk) in enumerate(((0, 1 / 3), (1, 2 / 3))):
        p = [0.0, 0.0, 0.0]
        p[ax] = seite
        p[lang] = lo[lang] + rand if fl == 0 else hi[lang] - rand
        p[kurz] = lo[kurz] + (hi[kurz] - lo[kurz]) * fk
        stellen.append({"p": p, "richtung": [(1 if aussen_min else -1) if a == ax else 0 for a in (0, 1, 2)]})
    return stellen


def name(v: dict) -> str:
    return f"{v['d']}×{v['l']}"


def preis(v: dict) -> float:
    return PREIS_JE_MM[v["d"]] * v["l"]


def randabstand(v: dict) -> int:
    return 5 * v["d"]
