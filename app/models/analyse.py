"""Anonyme Analyse-Daten: was Leute entwerfen und bauen, um Parawerk zu verbessern.

Gespeichert wird nur, was das Möbel beschreibt: Wunsch in Worten, Maße, gelesene Konstruktion (Bauteilgraph),
Ergebnis der Selbstkontrolle, Größe und Teile des fertigen Bauplans. Nie gespeichert werden Fotos, Masken,
Entwurfsbilder (darauf ist die Wohnung zu sehen), Geräte-ID oder IP. Einträge eines Durchgangs hängen nur über
``lauf`` zusammen: ein Hash der zufälligen Masken-ID, aus dem sich nichts zurückrechnen lässt.

Anders als Bilder werden diese Einträge nicht nach 7 Tagen gelöscht.
"""
from __future__ import annotations

import hashlib
import json
import logging

from sqlalchemy import Boolean, Column, DateTime, Engine, Index, Integer, String, Table, Text, insert, select

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


def lauf(zufalls_id: str | None) -> str | None:
    """Kurzer, nicht umkehrbarer Schlüssel aus einer zufälligen Bild-ID, um Einträge eines Durchgangs zu verbinden."""
    return hashlib.sha256(f"parawerk-lauf:{zufalls_id}".encode()).hexdigest()[:16] if zufalls_id else None


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
