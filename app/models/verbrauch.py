"""Verbrauch der KI-Dienste: jede Runde, jede Änderung, jede Lesung mit Gerät, IP und Kosten.

Lokal und in Tests SQLite, auf fly.io Postgres (``DATABASE_URL``). Die Tabelle ist zugleich der Kostendeckel:
Kontingente und Tagesbudget sind Zählungen und Summen über sie.
"""
from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from sqlalchemy import (Column, DateTime, Engine, Float, Index, Integer, MetaData, String, Table, UniqueConstraint,
                        create_engine, delete, func, insert, select)
from sqlalchemy.exc import IntegrityError

metadata = MetaData()

verbrauch = Table(
    "verbrauch", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("zeit", DateTime(timezone=True), nullable=False),
    Column("geraet", String(64), nullable=False),
    Column("ip", String(64), nullable=False),
    Column("art", String(32), nullable=False),  # runde, nachjustieren, lesen, anpassen
    Column("kosten_usd", Float, nullable=False),
    Index("ix_verbrauch_geraet_art", "geraet", "art"),
    Index("ix_verbrauch_zeit", "zeit"),
)

# Eingelöste Testcodes: welches Gerät hat welchen Code (je Code und Gerät nur einmal)
einloesungen = Table(
    "einloesungen", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("code", String(64), nullable=False),
    Column("geraet", String(64), nullable=False),
    Column("zeit", DateTime(timezone=True), nullable=False),
    UniqueConstraint("code", "geraet", name="uq_einloesung"),
)

STANDARD_URL = f"sqlite:///{Path(tempfile.gettempdir()) / 'parawerk.db'}"


def _url(url: str) -> str:
    """fly.io liefert postgres://…; SQLAlchemy braucht den Treiber im Namen."""
    for alt in ("postgres://", "postgresql://"):
        if url.startswith(alt):
            return "postgresql+psycopg://" + url[len(alt):]
    return url


@lru_cache
def datenbank(url: str = "") -> Engine:
    from . import analyse, speicher  # noqa: F401  (Tabellen für Bilder, Aufträge und Analyse registrieren)
    engine = create_engine(_url(url or STANDARD_URL), pool_pre_ping=True)
    metadata.create_all(engine)
    return engine


def jetzt() -> datetime:
    return datetime.now(timezone.utc)


def heute_beginn() -> datetime:
    return jetzt().replace(hour=0, minute=0, second=0, microsecond=0)


def eintragen(db: Engine, geraet: str, ip: str, art: str, kosten: float) -> int:
    with db.begin() as c:
        return c.execute(insert(verbrauch).values(zeit=jetzt(), geraet=geraet, ip=ip, art=art, kosten_usd=kosten)
                         .returning(verbrauch.c.id)).scalar_one()


def streichen(db: Engine, eintrag: int) -> None:
    with db.begin() as c:
        c.execute(delete(verbrauch).where(verbrauch.c.id == eintrag))


def anzahl(db: Engine, art: str, *, geraet: str | None = None, ip: str | None = None, seit: datetime | None = None) -> int:
    q = select(func.count()).select_from(verbrauch).where(verbrauch.c.art == art)
    if geraet is not None:
        q = q.where(verbrauch.c.geraet == geraet)
    if ip is not None:
        q = q.where(verbrauch.c.ip == ip)
    if seit is not None:
        q = q.where(verbrauch.c.zeit >= seit)
    with db.connect() as c:
        return c.execute(q).scalar_one()


def kosten_seit(db: Engine, seit: datetime) -> float:
    with db.connect() as c:
        return float(c.execute(select(func.coalesce(func.sum(verbrauch.c.kosten_usd), 0.0))
                               .where(verbrauch.c.zeit >= seit)).scalar_one())


def code_einloesen(db: Engine, code: str, geraet: str) -> None:
    """Trägt die Einlösung ein; hat das Gerät den Code schon, passiert nichts."""
    try:
        with db.begin() as c:
            c.execute(insert(einloesungen).values(code=code, geraet=geraet, zeit=jetzt()))
    except IntegrityError:
        pass


def codes_von(db: Engine, geraet: str) -> list[str]:
    with db.connect() as c:
        return [z.code for z in c.execute(select(einloesungen.c.code).where(einloesungen.c.geraet == geraet))]


def geraete_mit_code(db: Engine, code: str) -> int:
    with db.connect() as c:
        return c.execute(select(func.count()).select_from(einloesungen).where(einloesungen.c.code == code)).scalar_one()
