"""Bilder und Aufträge der App-API, in derselben Datenbank wie der Verbrauch.

Bilder (Fotos, Masken, Entwürfe) bekommen eine zufällige, nicht erratbare ID und werden nach
``AUFBEWAHRUNG`` gelöscht. Aufträge halten Status und Ergebnis lange laufender KI-Aufrufe.
"""
from __future__ import annotations

import json
import secrets
from datetime import timedelta

from sqlalchemy import Column, DateTime, Engine, Index, LargeBinary, String, Table, Text, delete, insert, select, update

from .verbrauch import jetzt, metadata

AUFBEWAHRUNG = timedelta(days=7)

bilder = Table(
    "bilder", metadata,
    Column("id", String(32), primary_key=True),
    Column("geraet", String(64), nullable=False),
    Column("mime", String(32), nullable=False),
    Column("daten", LargeBinary, nullable=False),
    Column("erstellt", DateTime(timezone=True), nullable=False),
    Index("ix_bilder_erstellt", "erstellt"),
)

auftraege = Table(
    "auftraege", metadata,
    Column("id", String(32), primary_key=True),
    Column("geraet", String(64), nullable=False),
    Column("art", String(32), nullable=False),
    Column("status", String(16), nullable=False),  # laeuft, fertig, fehler
    Column("ergebnis", Text),  # JSON
    Column("fehler", Text),
    Column("erstellt", DateTime(timezone=True), nullable=False),
    Index("ix_auftraege_erstellt", "erstellt"),
)


def neue_id() -> str:
    return secrets.token_hex(16)


def bild_speichern(db: Engine, geraet: str, daten: bytes, mime: str) -> str:
    bid = neue_id()
    with db.begin() as c:
        c.execute(insert(bilder).values(id=bid, geraet=geraet, mime=mime, daten=daten, erstellt=jetzt()))
    return bid


def bild_laden(db: Engine, bid: str) -> tuple[bytes, str] | None:
    with db.connect() as c:
        z = c.execute(select(bilder.c.daten, bilder.c.mime).where(bilder.c.id == bid)).first()
    return (bytes(z.daten), z.mime) if z else None


def auftrag_anlegen(db: Engine, geraet: str, art: str) -> str:
    aid = neue_id()
    with db.begin() as c:
        c.execute(insert(auftraege).values(id=aid, geraet=geraet, art=art, status="laeuft", erstellt=jetzt()))
    return aid


def auftrag_beenden(db: Engine, aid: str, ergebnis: dict | None = None, fehler: str | None = None) -> None:
    werte = {"status": "fehler", "fehler": fehler} if fehler is not None else \
        {"status": "fertig", "ergebnis": json.dumps(ergebnis, ensure_ascii=False)}
    with db.begin() as c:
        c.execute(update(auftraege).where(auftraege.c.id == aid).values(**werte))


def auftrag_laden(db: Engine, aid: str) -> dict | None:
    with db.connect() as c:
        z = c.execute(select(auftraege).where(auftraege.c.id == aid)).first()
    if not z:
        return None
    return {"id": z.id, "geraet": z.geraet, "art": z.art, "status": z.status,
            "ergebnis": json.loads(z.ergebnis) if z.ergebnis else None, "fehler": z.fehler}


def aufraeumen(db: Engine) -> None:
    """Alte Bilder und Aufträge löschen (Fotos aus Wohnungen nicht länger als nötig aufheben)."""
    grenze = jetzt() - AUFBEWAHRUNG
    with db.begin() as c:
        c.execute(delete(bilder).where(bilder.c.erstellt < grenze))
        c.execute(delete(auftraege).where(auftraege.c.erstellt < grenze))
