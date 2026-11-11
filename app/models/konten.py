"""Konten über „Mit Apple anmelden“ und „Mit Google anmelden“, und Freischaltungen von Bauplänen.

Die App bzw. Website holt sich bei Apple oder Google ein ID-Token, der Server prüft es (``services/anmeldung.py``)
und legt eine Sitzung an (Cookie im Browser, Token in der App). Gespeichert wird nur, was das Konto erkennt:
Anbieter, die Nutzer-ID des Anbieters und, falls mitgeschickt, die E-Mail-Adresse. Sitzungen nur als Hash.

Ein Konto bündelt Kontingente und eingelöste Testcodes über Geräte hinweg (``k-<id>`` statt der Geräte-ID).
Freischaltungen gehören dem Konto (oder ohne Konto dem Gerät) und gelten je Entwurf: Änderungen an Größe, Sitz und
per Text an diesem Entwurf sind inklusive.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import Column, DateTime, Engine, Integer, String, Table, UniqueConstraint, func, insert, select, update
from sqlalchemy.exc import IntegrityError

from .projekte import alle_loeschen as projekte_alle_loeschen
from .verbrauch import jetzt, metadata

SITZUNG_GUELTIG = timedelta(days=365)
ANBIETER = ("apple", "google", "demo")

konten = Table(
    "konten", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("anbieter", String(16), nullable=False),
    Column("sub", String(255), nullable=False),  # feste Nutzer-ID beim Anbieter
    Column("email", String(254)),  # Apple schickt sie nur beim ersten Mal, evtl. als Weiterleitungsadresse
    Column("erstellt", DateTime(timezone=True), nullable=False),
    UniqueConstraint("anbieter", "sub", name="uq_konto_anbieter"),
)

sitzungen = Table(
    "sitzungen", metadata,
    Column("token_hash", String(64), primary_key=True),
    Column("konto", Integer, nullable=False),
    Column("erstellt", DateTime(timezone=True), nullable=False),
)

freischaltungen = Table(
    "freischaltungen", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("wer", String(64), nullable=False),  # k-<konto> oder Geräte-ID
    Column("plan", String(80), nullable=False),  # e-<entwurf_id> oder g-<hash des Graphen>
    Column("quelle", String(32), nullable=False),  # code:<CODE>, zahlung:<anbieter>, admin
    Column("zeit", DateTime(timezone=True), nullable=False),
    UniqueConstraint("wer", "plan", name="uq_freischaltung"),
)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def anmelden(db: Engine, anbieter: str, sub: str, email: str | None) -> str:
    """Konto zu (Anbieter, Nutzer-ID) holen oder anlegen und eine Sitzung starten. Gibt das Sitzungs-Token zurück."""
    with db.begin() as c:
        z = c.execute(select(konten.c.id, konten.c.email).where(konten.c.anbieter == anbieter,
                                                                konten.c.sub == sub)).first()
        if z is None:
            try:
                with c.begin_nested():
                    konto = c.execute(insert(konten).values(anbieter=anbieter, sub=sub, email=email,
                                                            erstellt=jetzt())).inserted_primary_key[0]
            except IntegrityError:  # gleichzeitig angelegt
                konto = c.execute(select(konten.c.id).where(konten.c.anbieter == anbieter,
                                                            konten.c.sub == sub)).scalar_one()
        else:
            konto = z.id
            if email and not z.email:
                c.execute(update(konten).where(konten.c.id == konto).values(email=email))
        token = secrets.token_urlsafe(32)
        c.execute(insert(sitzungen).values(token_hash=_hash(token), konto=konto, erstellt=jetzt()))
    return token


def konto_zur_sitzung(db: Engine, token: str) -> tuple[int, str] | None:
    """(Konto-ID, Anzeigename) zu einem Sitzungs-Token, oder None. Anzeigename: E-Mail oder Anbieter."""
    if not token:
        return None
    with db.connect() as c:
        z = c.execute(select(konten.c.id, konten.c.email, konten.c.anbieter).join(
            sitzungen, sitzungen.c.konto == konten.c.id).where(
            sitzungen.c.token_hash == _hash(token), sitzungen.c.erstellt >= jetzt() - SITZUNG_GUELTIG)).first()
    return (z.id, z.email or z.anbieter.capitalize()) if z else None


def abmelden(db: Engine, token: str) -> None:
    with db.begin() as c:
        c.execute(sitzungen.delete().where(sitzungen.c.token_hash == _hash(token)))


def konto_loeschen(db: Engine, konto: int) -> None:
    """Konto mit allem löschen (Pflicht für Apps mit Konto im App Store). Freischaltungen gehen dabei verloren."""
    with db.begin() as c:
        c.execute(sitzungen.delete().where(sitzungen.c.konto == konto))
        c.execute(freischaltungen.delete().where(freischaltungen.c.wer == f"k-{konto}"))
        projekte_alle_loeschen(None, f"k-{konto}", c)  # Projekte mit Wohnungsfotos gehören zum Konto
        c.execute(konten.delete().where(konten.c.id == konto))


def plan_schluessel(entwurf_id: str | None, graph: dict) -> str:
    """Wofür bezahlt wird: der gewählte Entwurf; ohne Entwurf der Graph ohne Größe und Sitz (die sind inklusive)."""
    if entwurf_id:
        return f"e-{entwurf_id}"
    import json

    from .bauteilgraph import bereinigen
    try:
        graph = bereinigen(graph)  # gleich gerechnet wie die Engine, egal wie der Graph geschickt wurde
    except (ValueError, KeyError, TypeError):
        pass
    kern = {k: v for k, v in graph.items() if k not in ("ziel", "sitz")}
    return "g-" + _hash(json.dumps(kern, sort_keys=True, ensure_ascii=False))[:40]


def freigeschaltet(db: Engine, wer: str, plan: str) -> bool:
    with db.connect() as c:
        return c.execute(select(freischaltungen.c.id).where(freischaltungen.c.wer == wer,
                                                            freischaltungen.c.plan == plan)).first() is not None


def freischalten(db: Engine, wer: str, plan: str, quelle: str) -> bool:
    """Bauplan freischalten (Code, Zahlung oder Admin). False, wenn er schon freigeschaltet war."""
    try:
        with db.begin() as c:
            c.execute(insert(freischaltungen).values(wer=wer, plan=plan, quelle=quelle[:32], zeit=jetzt()))
        return True
    except IntegrityError:
        return False


def freischaltungen_mit(db: Engine, wer: str, quelle: str) -> int:
    with db.connect() as c:
        return c.execute(select(func.count()).select_from(freischaltungen).where(
            freischaltungen.c.wer == wer, freischaltungen.c.quelle == quelle)).scalar_one()
