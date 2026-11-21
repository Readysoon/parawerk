"""Lerndaten hängen nur über zufällige IDs zusammen, nicht über nachrechenbare Hashes."""
import hashlib
import json
from datetime import timedelta

from sqlalchemy import select, update

from app.models import analyse, speicher
from app.models.verbrauch import datenbank
from app.umschluesseln import umschluesseln


def _db(tmp_path):
    return datenbank(f"sqlite:///{tmp_path / 't.db'}")


def test_gleiche_bild_id_gleiche_analyse_id(tmp_path):
    db = _db(tmp_path)
    a = analyse.lauf(db, "entwurf-1")
    assert a == analyse.lauf(db, "entwurf-1")
    assert a != analyse.lauf(db, "entwurf-2")
    assert analyse.lauf(db, None) is None


def test_nicht_nachrechenbar(tmp_path):
    db = _db(tmp_path)
    a = analyse.lauf(db, "entwurf-1")
    alt = hashlib.sha256(b"parawerk-lauf:entwurf-1").hexdigest()[:16]
    assert a != alt and a != hashlib.sha256(b"entwurf-1").hexdigest()[:16]


def test_zuordnung_wird_aufgeraeumt(tmp_path):
    db = _db(tmp_path)
    a = analyse.lauf(db, "entwurf-1")
    with db.begin() as c:
        c.execute(update(speicher.analyse_ids).values(erstellt=speicher.jetzt() - timedelta(days=8)))
    speicher.aufraeumen(db)
    with db.connect() as c:
        assert c.execute(select(speicher.analyse_ids)).first() is None
    assert analyse.lauf(db, "entwurf-1") != a  # danach führt nichts mehr zum alten Eintrag


def test_umschluesseln_ersetzt_alte_hashes(tmp_path):
    db = _db(tmp_path)
    alt = hashlib.sha256(b"parawerk-lauf:entwurf-1").hexdigest()[:16]
    analyse.eintragen(db, "gelesen", {"entwurf": alt}, lauf_id="lauf-alt")
    analyse.eintragen(db, "pdf", {"entwurf": alt}, lauf_id="lauf-alt")
    analyse.bild_eintragen(db, "entwurf", b"\xff\xd8jpeg", lauf_id="lauf-alt", entwurf=alt)
    umschluesseln(db)
    with db.connect() as c:
        zeilen = c.execute(select(analyse.analyse)).all()
        bild = c.execute(select(analyse.analyse_bilder)).first()
    entwuerfe = {json.loads(z.daten)["entwurf"] for z in zeilen}
    assert len(entwuerfe) == 1 and alt not in entwuerfe  # ersetzt, aber weiter zusammen
    assert {z.lauf for z in zeilen} == {bild.lauf} and bild.lauf != "lauf-alt"
    assert bild.entwurf in entwuerfe
