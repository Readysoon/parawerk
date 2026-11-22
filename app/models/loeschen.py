"""Datenschutz: Daten einer Person löschen und alte Daten aufräumen.

- ``alles_zu(c, wer)``: alles, was an einem Gerät (Geräte-ID) bzw. Konto (``k-<id>``) hängt. Genutzt beim Löschen des
  Kontos und bei „Meine Daten löschen“ ohne Konto.
- ``aufraeumen(db)``: Fristen aus der Datenschutzerklärung durchsetzen (Bilder 7 Tage, IP-Adressen 30 Tage, abgelaufene
  Sitzungen) und früher gespeicherte E-Mail-Adressen leeren. Läuft beim Start des Servers und bei jedem Foto-Upload.

Der Verbrauch wird beim Löschen nicht gelöscht, sondern vom Gerät getrennt (``geraet = "geloescht"``): Das Tagesbudget
und die Grenze je IP-Adresse rechnen weiter richtig, und die IP verschwindet ohnehin nach 30 Tagen.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import Engine, delete, or_, select, update

from . import speicher
from .konten import SITZUNG_GUELTIG, freischaltungen, konten, sitzungen
from .projekte import alle_loeschen as projekte_alle_loeschen, projekt_fotos, projekte
from .verbrauch import einloesungen, jetzt, verbrauch

IP_FRIST = timedelta(days=30)
GELOESCHT = "geloescht"


def alles_zu(c, wer: str) -> None:
    """Alles zu ``wer`` (Geräte-ID oder ``k-<konto>``) in der laufenden Transaktion ``c`` löschen."""
    # Zuordnungen Bild → Analyse-ID zuerst, solange die Bild-IDs noch bekannt sind (die Lerndaten selbst bleiben)
    bild_ids = select(speicher.bilder.c.id).where(speicher.bilder.c.geraet == wer)
    projekt_ids = select(projekte.c.id).where(projekte.c.wer == wer)
    c.execute(delete(speicher.analyse_ids).where(or_(
        speicher.analyse_ids.c.bild.in_(bild_ids),
        speicher.analyse_ids.c.bild.in_(select(projekte.c.entwurf_id).where(projekte.c.wer == wer)),
        speicher.analyse_ids.c.bild.in_(select(projekt_fotos.c.foto_id).where(projekt_fotos.c.projekt_id.in_(projekt_ids))),
        speicher.analyse_ids.c.bild.in_(select(projekt_fotos.c.maske_id).where(projekt_fotos.c.projekt_id.in_(projekt_ids))),
    )))
    projekte_alle_loeschen(None, wer, c)
    c.execute(delete(speicher.bilder).where(speicher.bilder.c.geraet == wer))
    c.execute(delete(speicher.auftraege).where(speicher.auftraege.c.geraet == wer))
    c.execute(delete(freischaltungen).where(freischaltungen.c.wer == wer))
    c.execute(delete(einloesungen).where(einloesungen.c.geraet == wer))
    c.execute(update(verbrauch).where(verbrauch.c.geraet == wer).values(geraet=GELOESCHT))


def geraet_loeschen(db: Engine, geraet: str) -> None:
    with db.begin() as c:
        alles_zu(c, geraet)


def aufraeumen(db: Engine) -> None:
    speicher.aufraeumen(db)  # Bilder, Aufträge, Analyse-Zuordnungen: 7 Tage
    with db.begin() as c:
        c.execute(update(verbrauch).where(verbrauch.c.zeit < jetzt() - IP_FRIST, verbrauch.c.ip != "")
                  .values(ip=""))
        c.execute(delete(sitzungen).where(sitzungen.c.erstellt < jetzt() - SITZUNG_GUELTIG))
        c.execute(update(konten).where(konten.c.email.isnot(None)).values(email=None))  # alte E-Mails (bis 22.11.2026)
