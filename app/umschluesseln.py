"""Einmalig: alte Hashes in den Lerndaten durch zufällige IDs ersetzen. ``python -m app.umschluesseln``.

Früher waren ``lauf`` und ``entwurf`` ein Hash der Bild-ID mit festem Präfix. Wer die Datenbank hatte, konnte ihn aus
den Entwurfs-IDs in ``freischaltungen`` und ``projekte`` nachrechnen und so Lerndaten einem Konto zuordnen. Dieses
Skript ersetzt jeden alten Wert durch eine neue Zufalls-ID, überall gleich: Was zusammengehörte, gehört weiter
zusammen, aber ohne Weg zurück. Danach ``analyse_ids`` leeren, damit auch laufende Durchgänge neu beginnen.

Läuft in einer Transaktion. Mehrfaches Ausführen schadet nicht (dann werden die Zufalls-IDs nur neu gewürfelt).
"""
from __future__ import annotations

import json
import os
import secrets

from sqlalchemy import Engine, delete, select, update

from .models.analyse import analyse, analyse_bilder
from .models.speicher import analyse_ids
from .models.verbrauch import datenbank

FELDER = ("entwurf", "vorher")  # JSON-Felder in analyse.daten, die eine Analyse-ID tragen


def umschluesseln(db: Engine) -> dict[str, int]:
    neu: dict[str, str] = {}

    def ersatz(alt: str | None) -> str | None:
        if not alt:
            return alt
        if alt not in neu:
            neu[alt] = secrets.token_hex(8)
        return neu[alt]

    zeilen = {"analyse": 0, "analyse_bilder": 0}
    with db.begin() as c:
        for z in c.execute(select(analyse.c.id, analyse.c.lauf, analyse.c.daten)).all():
            daten = json.loads(z.daten)
            for f in FELDER:
                if isinstance(daten.get(f), str):
                    daten[f] = ersatz(daten[f])
            c.execute(update(analyse).where(analyse.c.id == z.id).values(
                lauf=ersatz(z.lauf), daten=json.dumps(daten, ensure_ascii=False)))
            zeilen["analyse"] += 1
        for z in c.execute(select(analyse_bilder.c.id, analyse_bilder.c.lauf, analyse_bilder.c.entwurf)).all():
            c.execute(update(analyse_bilder).where(analyse_bilder.c.id == z.id).values(
                lauf=ersatz(z.lauf), entwurf=ersatz(z.entwurf)))
            zeilen["analyse_bilder"] += 1
        c.execute(delete(analyse_ids))
    return zeilen


if __name__ == "__main__":
    url = os.environ.get("DATABASE_URL", "sqlite:///parawerk.db")
    print(umschluesseln(datenbank(url)))
