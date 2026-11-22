"""Datenschutz: „Meine Daten herunterladen“ (DSGVO Art. 15 Auskunft und Art. 20 Datenübertragbarkeit).

Alles, was an einem Gerät (Geräte-ID) bzw. Konto (``k-<id>``) hängt, als eine JSON-Datei: Konto, Projekte mit
Zimmerfoto, Markierung und Entwurfsbild, Bilder der letzten 7 Tage, Freischaltungen, eingelöste Codes und der
Verbrauch (mit IP-Adresse, solange sie noch gespeichert ist). Bilder als data-URL, damit die Datei für sich steht.

Nicht dabei: die anonymen Lerndaten (sie lassen sich niemandem zuordnen) und interne Kostenschätzungen.
"""
from __future__ import annotations

import base64
import json

from sqlalchemy import Engine, select

from . import speicher, tresor
from .konten import freischaltungen, konten
from .projekte import projekt_fotos, projekte
from .verbrauch import einloesungen, jetzt, verbrauch

MIME_TIEFE = "application/x-parawerk-tiefe"


def _data_url(daten: bytes | None, mime: str) -> str | None:
    return f"data:{mime};base64," + base64.b64encode(daten).decode() if daten else None


def _zeit(z) -> str | None:
    return z.isoformat() if z else None


def meine_daten(db: Engine, wer: str, konto: int | None = None) -> dict:
    with db.connect() as c:
        k = c.execute(select(konten).where(konten.c.id == konto)).first() if konto else None
        pz = c.execute(select(projekte).where(projekte.c.wer == wer).order_by(projekte.c.erstellt)).all()
        fotos = {f.projekt_id: f for f in c.execute(select(projekt_fotos).where(
            projekt_fotos.c.projekt_id.in_([p.id for p in pz])))} if pz else {}
        bz = c.execute(select(speicher.bilder).where(speicher.bilder.c.geraet == wer)
                       .order_by(speicher.bilder.c.erstellt)).all()
        fz = c.execute(select(freischaltungen).where(freischaltungen.c.wer == wer)).all()
        cz = c.execute(select(einloesungen).where(einloesungen.c.geraet == wer)).all()
        vz = c.execute(select(verbrauch.c.zeit, verbrauch.c.art, verbrauch.c.ip).where(verbrauch.c.geraet == wer)
                       .order_by(verbrauch.c.zeit)).all()

    def projekt(p) -> dict:
        f = fotos.get(p.id)
        return {"id": p.id, "name": p.name, "erstellt": _zeit(p.erstellt), "geaendert": _zeit(p.geaendert),
                "konstruktion": json.loads(p.graph), "bereich_mm": json.loads(p.bereich), "masse_mm": json.loads(p.masse),
                "entwurfsbild": _data_url(tresor.auf(p.bild), "image/jpeg"),
                "wunsch": f.wunsch if f else None,
                "zimmerfoto": _data_url(tresor.auf(f.foto), f.foto_mime) if f else None,
                "markierung": _data_url(tresor.auf(f.maske), f.maske_mime) if f else None}

    return {
        "erstellt": _zeit(jetzt()),
        "hinweis": "Ihre bei Parawerk gespeicherten Daten (DSGVO Art. 15 und 20). Bilder sind als data-URL enthalten.",
        "konto": {"anbieter": k.anbieter, "email": k.email, "erstellt": _zeit(k.erstellt)} if k else None,
        "geraet": None if konto else wer,
        "projekte": [projekt(p) for p in pz],
        "bilder_letzte_7_tage": [{"erstellt": _zeit(b.erstellt), "art": b.mime,
                                  "inhalt": _data_url(tresor.auf(b.daten), b.mime) if b.mime.startswith("image/") else None}
                                 for b in bz if b.mime != MIME_TIEFE],
        "freischaltungen": [{"plan": f.plan, "quelle": f.quelle, "zeit": _zeit(f.zeit)} for f in fz],
        "eingeloeste_codes": [{"code": e.code, "zeit": _zeit(e.zeit)} for e in cz],
        "nutzung": [{"zeit": _zeit(v.zeit), "art": v.art, "ip": v.ip or None} for v in vz],
    }
