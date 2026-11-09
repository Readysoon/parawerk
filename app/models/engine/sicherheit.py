"""Sicherheitsregeln, die über die Statik hinausgehen.

Hochbetten und Etagenbetten: Für Betten, deren Liegefläche (Oberkante Lattenrost/Liegefläche) 600 mm oder höher
über dem Boden liegt, gilt EN 747-1:2024 (Absturzsicherung, Spaltmaße, Leiter, eigene Lasten). Das prüft die Engine
noch nicht, deshalb werden solche Betten vorerst nicht berechnet.

Kippsicherung: Regale und andere Aufbewahrungsmöbel ab 600 mm Höhe ohne Wandleiste bekommen eine Wandbefestigung
(2 Kippsicherungen mit Dübeln) in Einkaufsliste und Anleitung, und die Prüfung weist darauf hin. Kinder klettern an
Regalen hoch; umkippende Möbel sind eine häufige Unfallursache.
"""
from __future__ import annotations

from .grundlagen import Bauteil, mm

HOCHBETT_AB = 600.0  # mm, Geltungsbereich EN 747-1:2024
KIPPSICHERUNG_AB = 600.0  # mm Gesamthöhe
KIPPSICHERUNG_PREIS = 6.0  # € für 2 Stück mit Dübeln und Schrauben
LIEGEN = {"liegeflaeche", "lattenrost"}


def liegehoehe(ms: list[Bauteil]) -> float | None:
    """Höhe der Liegefläche (Oberkante) über dem Boden, oder None ohne Liegefläche."""
    liegen = [m for m in ms if m.rolle in LIEGEN]
    if not liegen:
        return None
    boden = min(m.min[2] for m in ms)
    return max(m.max[2] for m in liegen) - boden


def ist_hochbett(ms: list[Bauteil], g: dict) -> float | None:
    """Liegehöhe in mm, wenn das Möbel ein Hoch- oder Etagenbett ist, sonst None."""
    h = liegehoehe(ms)
    return mm(h) if h is not None and h >= HOCHBETT_AB else None


def braucht_kippsicherung(ms: list[Bauteil], g: dict) -> bool:
    """Aufbewahrungsmöbel ab 600 mm Höhe, die nicht ohnehin an der Wand hängen."""
    if any(m.rolle == "wandleiste" for m in ms):
        return False
    regal = g.get("kategorie") == "regal" or any(m.rolle == "regalboden" for m in ms)
    hoehe = max(m.max[2] for m in ms) - min(m.min[2] for m in ms)
    return regal and hoehe >= KIPPSICHERUNG_AB


__all__ = ["ist_hochbett", "braucht_kippsicherung", "liegehoehe", "HOCHBETT_AB", "KIPPSICHERUNG_PREIS"]
