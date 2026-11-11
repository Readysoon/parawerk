"""Meine Projekte: berechnete Baupläne eines Nutzers (Konto ``k-<id>`` oder, vor der echten Anmeldung, Gerät).

Gespeichert wird nur, wenn die App darum bittet (nach dem Anmelde-Schritt). Ein Projekt je Entwurf: spätere
Änderungen (Größe, Sitz) überschreiben es. Das Entwurfsbild wird als eigene Kopie (verkleinert) aufgehoben, weil
die Bilder-Tabelle nach 7 Tagen geleert wird; ebenso Wohnungsfoto, Markierung und Wunsch (Tabelle projekt_fotos),
damit man ein altes Projekt weiter anpassen kann. Löschen: einzeln in der App oder mit dem Konto, alles zusammen.
Alle Bilder liegen verschlüsselt (tresor.py, Schlüssel DATEN_SCHLUESSEL). Die nächtliche Sicherung außerhalb von
fly.io lässt die Tabellen trotzdem weg.
"""
from __future__ import annotations

import json
import secrets

from sqlalchemy import Column, DateTime, Engine, LargeBinary, String, Table, Text, UniqueConstraint, delete, insert, \
    select, update

from . import tresor
from .verbrauch import jetzt, metadata

projekte = Table(
    "projekte", metadata,
    Column("id", String(32), primary_key=True),
    Column("wer", String(64), nullable=False, index=True),  # k-<konto> oder Geräte-ID
    Column("entwurf_id", String(32), nullable=False),
    Column("name", String(80), nullable=False),
    Column("graph", Text, nullable=False),  # JSON, mit Wunschmaßen (ziel) und Sitz
    Column("bereich", Text, nullable=False),  # JSON [B, T, H]
    Column("masse", Text, nullable=False),  # JSON [B, T, H] wie gebaut
    Column("bild", LargeBinary),  # JPEG des Entwurfs, verkleinert
    Column("erstellt", DateTime(timezone=True), nullable=False),
    Column("geaendert", DateTime(timezone=True), nullable=False),
    UniqueConstraint("wer", "entwurf_id", name="uq_projekt"),
)

# eigene Tabelle, damit bestehende Datenbanken keine neue Spalte brauchen
projekt_fotos = Table(
    "projekt_fotos", metadata,
    Column("projekt_id", String(32), primary_key=True),
    Column("foto_id", String(32), nullable=False),
    Column("foto", LargeBinary, nullable=False),
    Column("foto_mime", String(40), nullable=False),
    Column("maske_id", String(32), nullable=False),
    Column("maske", LargeBinary, nullable=False),
    Column("maske_mime", String(40), nullable=False),
    Column("wunsch", Text, nullable=False, default=""),
)


def speichern(db: Engine, wer: str, entwurf_id: str, name: str, graph: dict, bereich: list, masse: list,
              bild: bytes | None, fotos: dict | None = None) -> str:
    """Anlegen oder (gleicher Entwurf) aktualisieren. Gibt die Projekt-ID zurück.

    ``fotos``: foto_id, foto, foto_mime, maske_id, maske, maske_mime, wunsch – fürs spätere Weiteranpassen."""
    pid = _speichern(db, wer, entwurf_id, name, graph, bereich, masse, tresor.zu(bild) if bild else None)
    if fotos:
        fotos = {**fotos, "foto": tresor.zu(fotos["foto"]), "maske": tresor.zu(fotos["maske"])}
        with db.begin() as c:
            if not c.execute(select(projekt_fotos.c.projekt_id).where(projekt_fotos.c.projekt_id == pid)).first():
                c.execute(insert(projekt_fotos).values(projekt_id=pid, **fotos))
    return pid


def _speichern(db: Engine, wer: str, entwurf_id: str, name: str, graph: dict, bereich: list, masse: list,
               bild: bytes | None) -> str:
    jetzt_ = jetzt()
    werte = {"name": name[:80], "graph": json.dumps(graph, ensure_ascii=False), "bereich": json.dumps(list(bereich)),
             "masse": json.dumps(list(masse)), "geaendert": jetzt_}
    with db.begin() as c:
        z = c.execute(select(projekte.c.id, projekte.c.bild).where(projekte.c.wer == wer, projekte.c.entwurf_id == entwurf_id)).first()
        if z:
            if z.bild is None and bild:
                werte["bild"] = bild
            c.execute(update(projekte).where(projekte.c.id == z.id).values(**werte))
            return z.id
        pid = secrets.token_hex(16)
        c.execute(insert(projekte).values(id=pid, wer=wer, entwurf_id=entwurf_id, bild=bild, erstellt=jetzt_, **werte))
        return pid


def liste(db: Engine, wer: str) -> list[dict]:
    with db.connect() as c:
        zeilen = c.execute(select(projekte.c.id, projekte.c.name, projekte.c.masse, projekte.c.geaendert,
                                  projekte.c.bild.isnot(None).label("hat_bild"))
                           .where(projekte.c.wer == wer).order_by(projekte.c.geaendert.desc())).all()
    return [{"id": z.id, "name": z.name, "masse": json.loads(z.masse), "geaendert": z.geaendert.isoformat(),
             "hat_bild": bool(z.hat_bild)} for z in zeilen]


def laden(db: Engine, wer: str, pid: str) -> dict | None:
    with db.connect() as c:
        z = c.execute(select(projekte).where(projekte.c.id == pid, projekte.c.wer == wer)).first()
        f = c.execute(select(projekt_fotos).where(projekt_fotos.c.projekt_id == pid)).first() if z else None
    if not z:
        return None
    fotos = None
    if f:
        fotos = {**f._mapping, "foto": tresor.auf(f.foto), "maske": tresor.auf(f.maske)}
    return {"id": z.id, "name": z.name, "entwurf_id": z.entwurf_id, "graph": json.loads(z.graph),
            "bereich": json.loads(z.bereich), "masse": json.loads(z.masse), "bild": tresor.auf(z.bild),
            "fotos": fotos}


def bild(db: Engine, pid: str) -> bytes | None:
    """Vorschaubild; die Projekt-ID ist nicht zu erraten (wie bei den Bildern)."""
    with db.connect() as c:
        z = c.execute(select(projekte.c.bild).where(projekte.c.id == pid)).first()
    return tresor.auf(z.bild) if z else None


def loeschen(db: Engine, wer: str, pid: str) -> bool:
    with db.begin() as c:
        weg = c.execute(delete(projekte).where(projekte.c.id == pid, projekte.c.wer == wer)).rowcount > 0
        if weg:
            c.execute(delete(projekt_fotos).where(projekt_fotos.c.projekt_id == pid))
        return weg


def alle_loeschen(db: Engine, wer: str, c=None) -> None:
    """Alle Projekte samt Fotos (beim Löschen des Kontos; ``c`` = laufende Transaktion)."""
    if c is None:
        with db.begin() as c:
            return alle_loeschen(db, wer, c)
    ids = select(projekte.c.id).where(projekte.c.wer == wer)
    c.execute(delete(projekt_fotos).where(projekt_fotos.c.projekt_id.in_(ids)))
    c.execute(delete(projekte).where(projekte.c.wer == wer))


def uebernehmen(db: Engine, geraet: str, wer: str) -> None:
    """Nach der Anmeldung: Projekte des Geräts gehören dem Konto (gleicher Entwurf schon da → Gerätekopie weg)."""
    with db.begin() as c:
        vorhanden = {z.entwurf_id for z in c.execute(select(projekte.c.entwurf_id).where(projekte.c.wer == wer))}
        doppelt = select(projekte.c.id).where(projekte.c.wer == geraet, projekte.c.entwurf_id.in_(vorhanden))
        c.execute(delete(projekt_fotos).where(projekt_fotos.c.projekt_id.in_(doppelt)))
        c.execute(delete(projekte).where(projekte.c.wer == geraet, projekte.c.entwurf_id.in_(vorhanden)))
        c.execute(update(projekte).where(projekte.c.wer == geraet).values(wer=wer))
