"""Fotos liegen verschlüsselt in der Datenbank; ohne Schlüssel nicht lesbar, alte Einträge bleiben lesbar."""
from __future__ import annotations

import base64
import os

import pytest
from sqlalchemy import select

from app.models import speicher, tresor
from app.models.verbrauch import datenbank


@pytest.fixture
def schluessel(monkeypatch):
    monkeypatch.setenv("DATEN_SCHLUESSEL", base64.b64encode(os.urandom(32)).decode())
    tresor._schluessel.cache_clear()
    yield
    monkeypatch.delenv("DATEN_SCHLUESSEL")
    tresor._schluessel.cache_clear()


def test_bild_verschluesselt_gespeichert(schluessel, tmp_path):
    db = datenbank(f"sqlite:///{tmp_path / 't.db'}")
    bid = speicher.bild_speichern(db, "g", b"WOHNUNGSFOTO", "image/jpeg")
    with db.connect() as c:
        roh = c.execute(select(speicher.bilder.c.daten).where(speicher.bilder.c.id == bid)).scalar_one()
    assert roh.startswith(tresor.VORSPANN) and b"WOHNUNGSFOTO" not in roh
    assert speicher.bild_laden(db, bid) == (b"WOHNUNGSFOTO", "image/jpeg")
    # ohne Schlüssel: nicht lesbar
    os.environ["DATEN_SCHLUESSEL"] = ""
    tresor._schluessel.cache_clear()
    with pytest.raises(tresor.SchluesselFehlt):
        speicher.bild_laden(db, bid)


def test_alte_unverschluesselte_bilder_bleiben_lesbar(schluessel):
    assert tresor.auf(b"\xff\xd8altes jpeg") == b"\xff\xd8altes jpeg"
    assert tresor.auf(tresor.zu(b"neu")) == b"neu"
    assert tresor.zu(b"neu") != tresor.zu(b"neu")  # jedes Mal andere Nonce


def test_ohne_schluessel_unverschluesselt():
    tresor._schluessel.cache_clear()
    assert tresor.zu(b"x") == b"x"
