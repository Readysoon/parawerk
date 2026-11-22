"""Datenschutz: Daten löschen (Gerät, Konto) und Fristen (IP 30 Tage, abgelaufene Sitzungen)."""
from datetime import timedelta

from sqlalchemy import func, select, update

from app.models import analyse, konten, loeschen, projekte, speicher
from app.models.verbrauch import code_einloesen, datenbank, einloesungen, eintragen, jetzt, verbrauch


def _db(tmp_path):
    return datenbank(f"sqlite:///{tmp_path / 'l.db'}")


def _anzahl(db, tabelle, *bedingung):
    with db.connect() as c:
        return c.execute(select(func.count()).select_from(tabelle).where(*bedingung)).scalar_one()


def _daten_fuer(db, wer):
    bid = speicher.bild_speichern(db, wer, b"\xff\xd8foto", "image/jpeg")
    speicher.auftrag_anlegen(db, wer, "lesen")
    analyse.lauf(db, bid)
    projekte.speichern(db, wer, bid, "Bank", {"name": "Bank"}, [1, 1, 1], [1, 1, 1], b"bild",
                       {"foto_id": "f-" + wer, "foto": b"f", "foto_mime": "image/jpeg", "maske_id": "m-" + wer,
                        "maske": b"m", "maske_mime": "image/png", "wunsch": "Bank"})
    analyse.lauf(db, "m-" + wer)
    konten.freischalten(db, wer, f"e-{bid}", "code:TEST")
    code_einloesen(db, "TEST", wer)
    eintragen(db, wer, "1.2.3.4", "runde", 0.2)
    analyse.eintragen(db, "pdf", {"entwurf": analyse.lauf(db, bid)}, lauf_id=analyse.lauf(db, "m-" + wer))
    return bid


def _rest(db, wer):
    return {
        "bilder": _anzahl(db, speicher.bilder, speicher.bilder.c.geraet == wer),
        "auftraege": _anzahl(db, speicher.auftraege, speicher.auftraege.c.geraet == wer),
        "projekte": _anzahl(db, projekte.projekte, projekte.projekte.c.wer == wer),
        "freischaltungen": _anzahl(db, konten.freischaltungen, konten.freischaltungen.c.wer == wer),
        "codes": _anzahl(db, einloesungen, einloesungen.c.geraet == wer),
        "verbrauch": _anzahl(db, verbrauch, verbrauch.c.geraet == wer),
    }


def test_geraet_loeschen(tmp_path):
    db = _db(tmp_path)
    _daten_fuer(db, "geraet-a")
    _daten_fuer(db, "geraet-b")
    loeschen.geraet_loeschen(db, "geraet-a")
    assert set(_rest(db, "geraet-a").values()) == {0}
    assert set(_rest(db, "geraet-b").values()) == {1}  # andere bleiben
    assert _anzahl(db, speicher.analyse_ids) == 2  # nur noch die von geraet-b
    assert _anzahl(db, verbrauch, verbrauch.c.geraet == loeschen.GELOESCHT) == 1  # Budget zählt weiter
    assert _anzahl(db, analyse.analyse) == 2  # Lerndaten bleiben, ohne Spur zurück


def test_konto_loeschen_nimmt_alles_mit(tmp_path):
    db = _db(tmp_path)
    konten.anmelden(db, "demo", "nutzer-1", "a@example.com")
    with db.connect() as c:
        kid = c.execute(select(konten.konten.c.id)).scalar_one()
    _daten_fuer(db, f"k-{kid}")
    konten.konto_loeschen(db, kid)
    assert set(_rest(db, f"k-{kid}").values()) == {0}
    assert _anzahl(db, konten.konten) == 0 and _anzahl(db, konten.sitzungen) == 0
    assert _anzahl(db, speicher.analyse_ids) == 0


def test_aufraeumen_ip_nach_30_tagen(tmp_path):
    db = _db(tmp_path)
    alt, neu = eintragen(db, "g", "1.2.3.4", "runde", 0.2), eintragen(db, "g", "5.6.7.8", "runde", 0.2)
    with db.begin() as c:
        c.execute(update(verbrauch).where(verbrauch.c.id == alt).values(zeit=jetzt() - timedelta(days=31)))
    loeschen.aufraeumen(db)
    with db.connect() as c:
        ips = dict(c.execute(select(verbrauch.c.id, verbrauch.c.ip)).all())
    assert ips == {alt: "", neu: "5.6.7.8"}  # Zeile bleibt (Gratis-Runden zählen), nur die IP ist weg


def test_aufraeumen_abgelaufene_sitzungen(tmp_path):
    db = _db(tmp_path)
    token_alt = konten.anmelden(db, "demo", "nutzer-1", None)
    konten.anmelden(db, "demo", "nutzer-1", None)
    with db.begin() as c:
        c.execute(update(konten.sitzungen).where(konten.sitzungen.c.token_hash == konten._hash(token_alt))
                  .values(erstellt=jetzt() - konten.SITZUNG_GUELTIG - timedelta(days=1)))
    loeschen.aufraeumen(db)
    assert _anzahl(db, konten.sitzungen) == 1


def test_geraet_loeschen_ueber_die_api(tmp_path):
    from fastapi.testclient import TestClient

    from app.config import Einstellungen, einstellungen
    from app.main import app

    e = Einstellungen(_env_file=None, database_url=f"sqlite:///{tmp_path / 'api.db'}")
    app.dependency_overrides[einstellungen] = lambda: e
    try:
        db = datenbank(e.database_url)
        _daten_fuer(db, "geraet-api-123")
        with TestClient(app, headers={"X-Geraet": "geraet-api-123"}) as c:
            r = c.delete("/api/v1/geraet")
        assert r.status_code == 200 and r.json() == {"geloescht": True}
        assert set(_rest(db, "geraet-api-123").values()) == {0}
    finally:
        app.dependency_overrides.clear()


def test_meine_daten_herunterladen(tmp_path):
    import json

    from fastapi.testclient import TestClient

    from app.config import Einstellungen, einstellungen
    from app.main import app

    e = Einstellungen(_env_file=None, database_url=f"sqlite:///{tmp_path / 'aus.db'}")
    app.dependency_overrides[einstellungen] = lambda: e
    try:
        db = datenbank(e.database_url)
        _daten_fuer(db, "geraet-aus-123")
        _daten_fuer(db, "geraet-fremd-1")
        with TestClient(app, headers={"X-Geraet": "geraet-aus-123"}) as c:
            r = c.get("/api/v1/meine-daten")
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = json.loads(r.content)
    assert d["geraet"] == "geraet-aus-123" and d["konto"] is None
    assert len(d["projekte"]) == 1 and d["projekte"][0]["zimmerfoto"].startswith("data:image/jpeg;base64,")
    assert d["projekte"][0]["wunsch"] == "Bank"
    assert len(d["freischaltungen"]) == 1 and d["eingeloeste_codes"][0]["code"] == "TEST"
    assert d["nutzung"][0]["ip"] == "1.2.3.4"
    assert "geraet-fremd-1" not in r.text  # nur die eigenen Daten
