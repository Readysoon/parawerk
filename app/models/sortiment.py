"""Holz-Sortiment im Baumarkt.

DE: gehobelte Fichte, Stand Okt. 2026 (obi.de, toom.de, hornbach.at).
US: Bauholz nominal → tatsächlich (mm). 1x = 19 mm, 2x = 38 mm, Längen 8', 10', 12'.
"""
from __future__ import annotations

from typing import TypedDict


class Stab(TypedDict):
    a: int
    b: int
    L: list[int]
    label: str


class Leimholz(TypedDict):
    t: int
    W: list[int]
    L: int


class Sortiment(TypedDict):
    latte: list[Stab]
    kantholz: list[Stab]
    leimholz: list[Leimholz]


SORTIMENT_DE: Sortiment = {
    "latte": [{"a": 24, "b": 44, "L": [2000], "label": "Latte 24×44 gehobelt"}],
    "kantholz": [
        {"a": 34, "b": 54, "L": [2000], "label": "Rahmenholz 34×54 gehobelt"},
        {"a": 44, "b": 44, "L": [2000, 2500], "label": "Rahmenholz 44×44 gehobelt"},
        {"a": 44, "b": 74, "L": [2000, 2500], "label": "Rahmenholz 44×74 gehobelt"},
        {"a": 44, "b": 94, "L": [2000, 3000], "label": "Rahmenholz 44×94 gehobelt"},
    ],
    "leimholz": [{"t": 18, "W": [200, 400, 500, 600], "L": 2000}, {"t": 28, "W": [200, 300, 400, 500], "L": 2000}],
}

_US_L = [2438, 3048, 3658]
SORTIMENT_US: Sortiment = {
    "latte": [{"a": 19, "b": b, "L": list(_US_L), "label": n}
              for b, n in [(38, "1x2"), (64, "1x3"), (89, "1x4"), (140, "1x6"), (184, "1x8"), (235, "1x10"), (286, "1x12")]],
    "kantholz": [{"a": a, "b": b, "L": list(_US_L), "label": n}
                 for a, b, n in [(38, 38, "2x2"), (38, 64, "2x3"), (38, 89, "2x4"), (38, 140, "2x6"), (38, 184, "2x8"),
                                 (38, 235, "2x10"), (89, 89, "4x4")]],
    "leimholz": [{"t": 19, "W": [1220], "L": 2440}, {"t": 12, "W": [1220], "L": 2440}],
}

SORTIMENTE = {"DE": SORTIMENT_DE, "US": SORTIMENT_US}
SCHNITT_PREIS = 0.99  # € je gerader Schnitt (OBI-Zuschnittservice, Angabe obi.de)


def naechstes_kantholz(S: Sortiment, a: float, b: float) -> Stab:
    """Kantholz, dessen Querschnitt am nächsten an a × b liegt."""
    best = S["kantholz"][0]
    for p in S["kantholz"][1:]:
        if abs(p["a"] - a) + abs(p["b"] - b) < abs(best["a"] - a) + abs(best["b"] - b):
            best = p
    return best


def handelslaengen(S: Sortiment, m) -> list[int]:
    if m.typ in ("latte", "kantholz"):
        return next(p for p in S[m.typ] if p["label"] == m.prof["label"])["L"]
    return [next(p for p in S["leimholz"] if p["t"] == m.prof["t"])["L"]]
