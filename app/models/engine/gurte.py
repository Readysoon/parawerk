"""Sitz mit elastischen Polstergurten (Gummigurte, „Pirelli-Gurte“) statt Latten: weich und federnd.

Die Gurte (50 mm breit) werden quer über die Zargen gespannt, etwa 10 % kürzer zugeschnitten als die lichte Weite
(Vorspannung), und an beiden Enden mit Tackerklammern auf der Zarge befestigt. Obendrauf kommt ein Schaumpolster.

Für die Statik heißt das: Die Gurte selbst werden nicht als Holz gerechnet, sie ziehen aber die Zargen nach innen
(Vorspannung als Dauerlast, dazu der Zug, wenn jemand sitzt). Das rechnet ``statik.py``.
"""
from __future__ import annotations

import copy
import math

from .grundlagen import gesetzt

GURT_BREITE = 50  # mm
GURT_LUECKE = 30  # mm zwischen zwei Gurten
GURT_DICKE = 3  # mm, nur für die Darstellung
VORSPANNUNG = 0.10  # Gurt 10 % kürzer als die lichte Weite
EINZUG = 50  # mm Abstand der äußeren Gurte zur Kante (Seitenzarge)
UMSCHLAG = 40  # mm je Ende zum Festtackern
KLAMMERN_JE_ENDE = 4
POLSTER_MIN = 50  # mm Schaum auf Gurten (die Gurte federn selbst)
ZUG_VOR = 150.0  # N je Gurt aus der Vorspannung (Dauerlast)
ZUG_PERSON = 1100.0  # N waagrecht je Zarge, wenn jemand sitzt: 1300 N / (2·tan 30°) bei etwa 30° Durchhang


def gurt_rollen(g: dict) -> set[str]:
    """Welche Flächen Gurte werden: Sitzflächen immer, Latten unter einer Matratze nie (Lattenrost bleibt)."""
    f = g.get("funktion") or {}
    return {"sitzflaeche"} if gesetzt(f.get("matratze")) else {"sitzflaeche", "liegeflaeche", "lattenrost"}


def umstellen(g: dict) -> dict:
    """Graph mit Gurten statt Sitzlatten/-brettern (Kopie). Das Polster wird mindestens 10 cm dick."""
    neu = copy.deepcopy(g)
    rollen = gurt_rollen(neu)
    getroffen = False
    for teil in neu["teile"]:
        if teil.get("rolle") in rollen:
            teil["_war"] = teil.get("rolle")
            teil["typ"], teil["rolle"] = "gurt", "gurt"
            teil.pop("querschnitt", None)
            teil.pop("_profil", None)
            getroffen = True
    if getroffen:
        f = neu.setdefault("funktion", {})
        f["polster"] = max(f.get("polster") or 0, POLSTER_MIN)
    return neu


def anzahl(breite: float) -> int:
    """Gurte für eine Sitzbreite (quer zu den Gurten), mindestens 2."""
    return max(2, round((breite + GURT_LUECKE) / (GURT_BREITE + GURT_LUECKE)))


def zuschnitt(lichte_weite: float) -> float:
    """Länge eines Gurts: lichte Weite minus Vorspannung plus Umschlag an beiden Enden."""
    return lichte_weite * (1 - VORSPANNUNG) + 2 * UMSCHLAG


def meter(laengen: list[float]) -> float:
    """Gurtband zum Kaufen in Metern, auf halbe Meter aufgerundet."""
    return math.ceil(sum(laengen) / 500) / 2
