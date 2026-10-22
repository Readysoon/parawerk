"""Grundbausteine der Engine: Bauteil, Rollen, Quader-Geometrie.

Koordinaten: x = Breite (links → rechts), y = Tiefe (0 vorne → hinten/Wand), z = Höhe (0 = Boden).
Achsen werden als Index 0/1/2 geführt, alle Maße in mm.
"""
from __future__ import annotations

import copy
import math
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

AXN = ["x", "y", "z"]
AXI = {"x": 0, "y": 1, "z": 2}

# Je höher, desto eher bleibt ein Teil liegen, wenn sich zwei Teile ins Gehege kommen.
PRIO = {
    "riegel": 5, "wandleiste": 6, "bein": 6, "pfosten": 6, "kufe": 6, "stuetze": 6, "rahmen": 5, "zarge": 5,
    "auflage": 4, "mittelsteg": 4, "querriegel": 4, "leiste": 3, "lattenrost": 2, "sitzflaeche": 2,
    "liegeflaeche": 2, "regalboden": 2, "lehne": 2, "verkleidung": 1,
}
ROLLENNAME = {
    "riegel": "Fußriegel", "wandleiste": "Wandleiste", "bein": "Bein", "pfosten": "Pfosten", "kufe": "Kufe",
    "stuetze": "Stütze", "rahmen": "Rahmen", "zarge": "Zarge", "auflage": "Auflageleiste", "mittelsteg": "Mittelsteg",
    "querriegel": "Querriegel", "lattenrost": "Lattenrost", "sitzflaeche": "Sitzbrett", "liegeflaeche": "Liegefläche",
    "regalboden": "Regalboden", "leiste": "Leiste", "lehne": "Lehne", "verkleidung": "Verkleidung",
}
GRAVITY = {"lattenrost", "sitzflaeche", "liegeflaeche", "regalboden"}  # fällt auf das Teil darunter
LOADED = {"lattenrost", "sitzflaeche", "liegeflaeche", "regalboden", "auflage", "rahmen", "zarge", "mittelsteg", "querriegel"}
SLATS = {"lattenrost", "sitzflaeche", "liegeflaeche", "regalboden"}
ATTACH = {"auflage", "lehne", "verkleidung"}  # wird seitlich an einen Träger angelegt
TOL = 60  # größte Korrektur aus der Bildlesung (mm)
GAP = 12  # kleine Fugen, die geschlossen werden (mm)


class Bauteil:
    """Ein Holzteil als achsparalleler Quader.

    Zwei Bauteile sind nur gleich, wenn es dasselbe Objekt ist; ``in``, ``index`` und ``remove`` auf Listen
    arbeiten damit über die Identität, auch wenn zwei Teile gleiche Maße haben.
    """

    def __init__(self, **felder: Any) -> None:
        self.rolle = None
        self.__dict__.update(felder)

    def kopie(self, **aenderungen: Any) -> "Bauteil":
        neu = Bauteil(**copy.deepcopy(self.__dict__))
        neu.__dict__.update(aenderungen)
        return neu

    def als_dict(self) -> dict:
        return {
            "id": self.id, "part": self.part, "name": self.name, "typ": self.typ, "rolle": self.rolle,
            "prof": self.prof, "long": self.long, "dax": self.dax, "min": self.min, "max": self.max,
            "origin": self.origin,
        }

    def __repr__(self) -> str:
        return f"Bauteil({getattr(self, 'id', '?')})"


def quader(mn: Iterable[float], mx: Iterable[float]) -> Bauteil:
    """Reiner Quader zum Ausprobieren einer Verschiebung (ohne Rolle)."""
    return Bauteil(min=list(mn), max=list(mx))


def prio(m: Bauteil) -> int:
    return PRIO.get(m.rolle, 3)


def rollenname(rolle: str | None) -> str:
    return ROLLENNAME.get(rolle, str(rolle))


def ext(m: Bauteil, a: int) -> float:
    return m.max[a] - m.min[a]


def ov(a: Bauteil, b: Bauteil, ax: int) -> float:
    """Überlappung zweier Quader entlang einer Achse (negativ = Abstand)."""
    return min(a.max[ax], b.max[ax]) - max(a.min[ax], b.min[ax])


def cen(m: Bauteil, a: int) -> float:
    return (m.min[a] + m.max[a]) / 2


def others(a: int) -> list[int]:
    return [x for x in (0, 1, 2) if x != a]


def depth(a: Bauteil, b: Bauteil) -> float:
    """Eindringtiefe: kleinste Überlappung, wenn sich die Quader in allen drei Achsen schneiden."""
    p = [ov(a, b, ax) for ax in (0, 1, 2)]
    return min(p) if all(v > 0.5 for v in p) else 0


def pen_sum(m: Bauteil, ms: list[Bauteil]) -> float:
    s = 0
    for o in ms:
        if o is not m:
            s = s + depth(m, o)
    return s


def touches(m: Bauteil, o: Bauteil, ax: int, side: str) -> bool:
    """Liegt o an der Seite ``side`` von m entlang ``ax`` an?"""
    f = m.min[ax] if side == "min" else m.max[ax]
    g = o.max[ax] if side == "min" else o.min[ax]
    return abs(f - g) <= 0.6 and all(ov(m, o, c) > 2 for c in others(ax))


def seite(m: Bauteil, side: str) -> list[float]:
    return m.min if side == "min" else m.max


# ---------- Zahlen wie im Browser ----------
# Die Engine war zuerst in JavaScript geschrieben. Damit Bauplan-Texte und Rundungen identisch bleiben,
# runden und formatieren diese Helfer wie JavaScript.

def mm(v: float) -> int:
    """Auf ganze mm runden, .5 immer aufwärts (wie Math.round)."""
    return math.floor(v + 0.5)


def zahl(v: Any) -> str:
    """Zahl als Text ohne überflüssiges ``.0``."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        if math.isfinite(v) and v.is_integer() and abs(v) < 1e21:
            return str(int(v))
        if math.isnan(v):
            return "NaN"
        if math.isinf(v):
            return "Infinity" if v > 0 else "-Infinity"
    return str(v)


def fest(v: float, stellen: int) -> str:
    """Feste Nachkommastellen, .5 aufwärts (wie toFixed)."""
    q = Decimal(1).scaleb(-stellen)
    return str(Decimal(v).quantize(q, rounding=ROUND_HALF_UP))


def gesetzt(v: Any) -> bool:
    """Wahrheitswert wie in JavaScript: leere Listen zählen als gesetzt, 0 und None nicht."""
    if v is None or v is False:
        return False
    if isinstance(v, (int, float)):
        return v != 0 and not (isinstance(v, float) and math.isnan(v))
    if isinstance(v, str):
        return v != ""
    return True


def oder(v: Any, ersatz: Any) -> Any:
    return v if gesetzt(v) else ersatz


def max_or(werte: Iterable[float], leer: float = -math.inf) -> float:
    werte = list(werte)
    return max(werte) if werte else leer


def min_or(werte: Iterable[float], leer: float = math.inf) -> float:
    werte = list(werte)
    return min(werte) if werte else leer


def einmalig(werte: Iterable[Any]) -> list:
    return list(dict.fromkeys(werte))


def eintraege(d: dict) -> list[tuple]:
    """Einträge in der Reihenfolge eines JavaScript-Objekts: ganzzahlige Schlüssel aufsteigend zuerst."""
    def ganz(k: Any) -> bool:
        s = str(k)
        return s.isdigit() and (s == "0" or not s.startswith("0")) and int(s) < 2**32 - 1

    zahlen = sorted((k for k in d if ganz(k)), key=lambda k: int(str(k)))
    rest = [k for k in d if not ganz(k)]
    return [(k, d[k]) for k in zahlen + rest]
