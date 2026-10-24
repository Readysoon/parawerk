"""Zweisprachigkeit (Deutsch, Englisch).

Die Sprache gilt pro Anfrage (``ContextVar``): Die Middleware setzt sie aus Cookie, Header oder Browser-Sprache,
Engine, Controller und Templates lesen sie über ``t()``. Ohne Angabe gilt Deutsch.
"""
from __future__ import annotations

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

from . import de, de_ui, en, en_ui

SPRACHEN = ("de", "en")
STANDARD = "de"
KATALOG = {"de": {**de.TEXTE, **de_ui.TEXTE}, "en": {**en.TEXTE, **en_ui.TEXTE}}
NAMEN = {"de": "Deutsch", "en": "English"}

_sprache: ContextVar[str] = ContextVar("sprache", default=STANDARD)


def sprache() -> str:
    return _sprache.get()


def setze_sprache(s: str | None):
    """Setzt die Sprache für die laufende Anfrage; gibt das Token zum Zurücksetzen zurück."""
    return _sprache.set(s if s in SPRACHEN else STANDARD)


def zuruecksetzen(token) -> None:
    _sprache.reset(token)


@contextmanager
def in_sprache(s: str | None) -> Iterator[None]:
    token = setze_sprache(s)
    try:
        yield
    finally:
        zuruecksetzen(token)


def t(key: str, **werte) -> str:
    """Text zum Schlüssel in der aktuellen Sprache; fehlt er dort, der deutsche."""
    vorlage = KATALOG[sprache()].get(key) or KATALOG[STANDARD][key]
    return vorlage.format(**werte) if werte else vorlage


def texte(*praefixe: str) -> dict[str, str]:
    """Alle Texte mit diesen Präfixen in der aktuellen Sprache (für den Browser)."""
    basis = {k: v for k, v in KATALOG[STANDARD].items() if k.startswith(praefixe)}
    basis.update({k: v for k, v in KATALOG[sprache()].items() if k.startswith(praefixe)})
    return basis


def name(text: str) -> str:
    """Übersetzter Name aus den Beispielkonstruktionen, sonst unverändert."""
    return KATALOG[sprache()].get(f"name.{text}", text)


def dez(zahl_text: str) -> str:
    """Dezimaltrennzeichen der Sprache: 2,5 (de) bzw. 2.5 (en)."""
    return zahl_text.replace(".", ",") if sprache() == "de" else zahl_text


def zitat(text: str) -> str:
    return f"„{text}“" if sprache() == "de" else f"“{text}”"


def und(teile: list[str]) -> str:
    return f" {t('wort.und')} ".join(teile)


_HOLZ_EN = [
    (re.compile(r"^Latte (\S+) gehobelt$"), r"Planed batten \1"),
    (re.compile(r"^Rahmenholz (\S+) gehobelt$"), r"Planed timber \1"),
]


def holz(label: str) -> str:
    """Anzeigename eines Holzprofils. Intern bleibt das deutsche Label der Schlüssel ins Sortiment."""
    if sprache() == "en":
        for muster, ersatz in _HOLZ_EN:
            if muster.match(label):
                return muster.sub(ersatz, label)
    return label


def aus_header(accept_language: str | None) -> str:
    """Erste unterstützte Sprache aus dem Accept-Language-Header."""
    for teil in (accept_language or "").split(","):
        code = teil.split(";")[0].strip().lower()[:2]
        if code in SPRACHEN:
            return code
    return STANDARD
