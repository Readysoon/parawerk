"""Sicherung: Lerndaten und Konten drin, Fotos, Verbrauch (Geräte, IP) und Sitzungen nicht."""
from __future__ import annotations

import gzip
import sqlite3

from app.models import analyse
from app.models import speicher
from app.models import verbrauch as v
from app.sicherung import sichern


def test_sicherung_ohne_fotos_und_geraete(tmp_path):
    db = v.datenbank(f"sqlite:///{tmp_path / 'p.db'}")
    analyse.eintragen(db, "rueckmeldung", {"text": "wackelt"})
    analyse.bild_eintragen(db, "entwurf", b"\xff\xd8jpeg", lauf_id="abc", entwurf="def")
    speicher.bild_speichern(db, "geraet-1", b"FOTO", "image/jpeg")
    v.eintragen(db, "geraet-1", "1.2.3.4", "runde", 0.2)
    zeilen = sichern(tmp_path / "p.db", tmp_path / "s.db.gz")
    assert zeilen["analyse"] == 1 and zeilen["analyse_bilder"] == 1
    (tmp_path / "s.db").write_bytes(gzip.open(tmp_path / "s.db.gz").read())
    with sqlite3.connect(tmp_path / "s.db") as c:
        tabellen = {r[0] for r in c.execute("select name from sqlite_master where type='table'")}
    assert {"analyse", "analyse_bilder", "konten", "freischaltungen", "modelle"} <= tabellen
    assert not tabellen & {"bilder", "verbrauch", "sitzungen", "auftraege", "einloesungen"}
