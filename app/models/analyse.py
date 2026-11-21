"""Anonyme Analyse-Daten: was Leute entwerfen und bauen, um Parawerk zu verbessern.

Gespeichert wird nur, was das Möbel beschreibt: Wunsch in Worten, Maße, gelesene Konstruktion (Bauteilgraph),
Ergebnis der Selbstkontrolle, jeder berechnete Bauplan (Reparaturen, Statik, offene Punkte), Freischaltungen und
Rückmeldungen. Dazu die gemalten Möbel als Bild, aber nur die Pixel innerhalb der Markierung, die die Bild-KI selbst
gemalt hat; alles außerhalb ist weiß (vom Zimmer ist nichts zu sehen). Nie gespeichert werden Fotos, Masken, ganze
Entwurfsbilder, Geräte-ID, Konto oder IP.

Einträge hängen nur über zufällige Analyse-IDs zusammen: ``lauf`` (ein Durchgang, zur Maske) und ``entwurf`` in den
Daten (der gewählte Entwurf). Sie stehen nie bei Konto, Projekt oder Freischaltung. Die Zuordnung Bild-ID → Analyse-ID
liegt nur in ``speicher.analyse_ids`` und wird nach 7 Tagen ohne Nutzung gelöscht (früher: ein Hash der Bild-ID, den
jeder mit der Datenbank nachrechnen und so einem Konto zuordnen konnte).

Anders als Bilder werden diese Einträge nicht nach 7 Tagen gelöscht.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy import (Boolean, Column, DateTime, Engine, Index, Integer, LargeBinary, String, Table, Text, insert,
                        select)

from . import speicher
from .verbrauch import jetzt, metadata

log = logging.getLogger("parawerk.analyse")

analyse = Table(
    "analyse", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("zeit", DateTime(timezone=True), nullable=False),
    Column("art", String(32), nullable=False),  # entwuerfe, gelesen, angepasst, pdf
    Column("lauf", String(16)),  # gleicher Wert = gleicher Durchgang (Hash, nicht umkehrbar)
    Column("sprache", String(8)),
    Column("demo", Boolean, nullable=False, default=False),
    Column("daten", Text, nullable=False),  # JSON
    Index("ix_analyse_zeit", "zeit"),
)


analyse_bilder = Table(
    "analyse_bilder", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("zeit", DateTime(timezone=True), nullable=False),
    Column("art", String(32), nullable=False),  # entwurf, nachjustiert
    Column("lauf", String(16)),
    Column("entwurf", String(16)),  # Hash der Entwurfs-ID, wie ``entwurf`` in den Analyse-Einträgen
    Column("demo", Boolean, nullable=False, default=False),
    Column("daten", LargeBinary, nullable=False),  # JPEG
)


def lauf(db: Engine, bild_id: str | None) -> str | None:
    """Analyse-ID zu einer Bild-ID (Maske oder Entwurf), um Einträge zu verbinden. Zufällig, nicht nachrechenbar."""
    return speicher.analyse_id(db, bild_id)


def eintragen(db: Engine, art: str, daten: dict, *, lauf_id: str | None = None, sprache: str | None = None,
              demo: bool = False) -> None:
    """Einen Eintrag speichern. Schlägt das fehl, merkt der Nutzer nichts davon (Analyse ist kein Muss)."""
    try:
        with db.begin() as c:
            c.execute(insert(analyse).values(zeit=jetzt(), art=art, lauf=lauf_id, sprache=sprache, demo=demo,
                                             daten=json.dumps(daten, ensure_ascii=False)))
    except Exception:  # noqa: BLE001
        log.exception("Analyse-Eintrag %s nicht gespeichert", art)


def alle(db: Engine, art: str | None = None, mit_demo: bool = False) -> list[dict]:
    q = select(analyse).order_by(analyse.c.id)
    if art:
        q = q.where(analyse.c.art == art)
    if not mit_demo:
        q = q.where(analyse.c.demo.is_(False))
    with db.connect() as c:
        return [{"zeit": z.zeit.isoformat(), "art": z.art, "lauf": z.lauf, "sprache": z.sprache, "demo": z.demo,
                 **json.loads(z.daten)} for z in c.execute(q)]


def bild_eintragen(db: Engine, art: str, daten: bytes, *, lauf_id: str | None, entwurf: str | None,
                   demo: bool = False) -> int | None:
    """Gemaltes Möbel speichern (siehe oben: nur die Pixel in der Markierung). Fehler bleiben still."""
    try:
        with db.begin() as c:
            return c.execute(insert(analyse_bilder).values(zeit=jetzt(), art=art, lauf=lauf_id, entwurf=entwurf,
                                                           demo=demo, daten=daten)
                             .returning(analyse_bilder.c.id)).scalar_one()
    except Exception:  # noqa: BLE001
        log.exception("Analyse-Bild %s nicht gespeichert", art)
        return None


def bilder_liste(db: Engine, mit_demo: bool = False) -> list[dict]:
    q = select(analyse_bilder.c.id, analyse_bilder.c.zeit, analyse_bilder.c.art, analyse_bilder.c.lauf,
               analyse_bilder.c.entwurf, analyse_bilder.c.demo).order_by(analyse_bilder.c.id)
    if not mit_demo:
        q = q.where(analyse_bilder.c.demo.is_(False))
    with db.connect() as c:
        return [{"id": z.id, "zeit": z.zeit.isoformat(), "art": z.art, "lauf": z.lauf, "entwurf": z.entwurf,
                 "demo": z.demo} for z in c.execute(q)]


def bild_laden(db: Engine, bid: int) -> bytes | None:
    with db.connect() as c:
        return c.execute(select(analyse_bilder.c.daten).where(analyse_bilder.c.id == bid)).scalar_one_or_none()
