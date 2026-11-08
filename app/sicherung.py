"""Sicherung der Datenbank für außerhalb von fly.io: ``python -m app.sicherung ziel.db.gz``.

Eine Kopie der SQLite-Datenbank (konsistent über die Backup-Funktion von SQLite, auch während die App läuft), aber nur
mit dem, was sich nicht neu erzeugen lässt und keine Fotos enthält:

- ``analyse``, ``analyse_bilder``: die Lerndaten (ohne Fotos, Gerät, IP; siehe ``models/analyse.py``)
- ``konten``, ``freischaltungen``: wer hat welche Baupläne freigeschaltet bzw. gekauft
- ``modelle``: 3D-Modelle hinter den QR-Codes gedruckter Baupläne

Nicht dabei: Fotos und Entwurfsbilder (``bilder``, nach 7 Tagen ohnehin gelöscht), Aufträge, Sitzungen und der
Verbrauch mit Geräte-IDs und IP-Adressen. Läuft täglich über ``.github/workflows/sicherung.yml``.
"""
from __future__ import annotations

import gzip
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

BEHALTEN = ("analyse", "analyse_bilder", "konten", "freischaltungen", "modelle")


def sqlite_pfad(url: str) -> Path:
    if not url.startswith("sqlite:///"):
        raise SystemExit("Sicherung kann nur SQLite (DATABASE_URL=sqlite:///…)")
    return Path(url.removeprefix("sqlite:///"))


def sichern(quelle: Path, ziel: Path) -> dict[str, int]:
    """Kopie ohne Fotos und Gerätedaten, gzip-komprimiert. Gibt die Zeilen je Tabelle zurück."""
    with tempfile.TemporaryDirectory() as tmp:
        kopie = Path(tmp) / "s.db"
        with sqlite3.connect(f"file:{quelle}?mode=ro", uri=True) as alt, sqlite3.connect(kopie) as neu:
            alt.backup(neu)
        zeilen = {}
        with sqlite3.connect(kopie) as c:
            tabellen = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
            for name in tabellen:
                if name.startswith("sqlite_"):
                    continue
                if name in BEHALTEN:
                    zeilen[name] = c.execute(f'select count(*) from "{name}"').fetchone()[0]
                else:
                    c.execute(f'drop table "{name}"')
            c.commit()
        with sqlite3.connect(kopie) as c:  # VACUUM nicht in einer Transaktion
            c.isolation_level = None
            c.execute("vacuum")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        with open(kopie, "rb") as f, gzip.open(ziel, "wb") as g:
            shutil.copyfileobj(f, g)
    return zeilen


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python -m app.sicherung ziel.db.gz")
    from .config import Einstellungen
    url = Einstellungen().database_url or os.environ.get("DATABASE_URL", "")
    if not url:
        from .models.verbrauch import STANDARD_URL
        url = STANDARD_URL
    print(sichern(sqlite_pfad(url), Path(sys.argv[1])))
