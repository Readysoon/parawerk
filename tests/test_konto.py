"""Stufen: ohne Konto eine Runde, Konto für Anpassen/Umwandeln, Freischalten für den vollständigen Bauplan."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.main import app
from tests.hilfen import alte_graphen

PLATZ = [6000, 3000, 3000]


@pytest.fixture
def stufen(tmp_path):
    db = f"sqlite:///{tmp_path / 'k.db'}"
    e = Einstellungen(database_url=db, konto_pflicht=True, bezahlung_pflicht=True, testcodes="PARTNER:0:5:2")
    app.dependency_overrides[einstellungen] = lambda: e
    yield e
    app.dependency_overrides.pop(einstellungen, None)


def _anmelden(c: TestClient, wer: str = "test-nutzer-0001") -> str:
    r = c.post("/api/v1/konto/anmelden/demo", json={"id_token": wer + "-xxxxxxxxxxxxxxx"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_anmelden_und_abmelden(stufen):
    with TestClient(app, headers={"X-Geraet": "konto-test-001"}) as c:
        stand = c.get("/api/v1/konto").json()
        assert stand["email"] is None and stand["konto_pflicht"] and stand["demo"]
        token = _anmelden(c)
        assert c.get("/api/v1/konto", headers={"Authorization": f"Bearer {token}"}).json()["email"] == "Demo"
        assert _anmelden(c) != token  # gleiches Konto, neue Sitzung
        c.post("/api/v1/konto/abmelden", headers={"Authorization": f"Bearer {token}"})
        assert c.get("/api/v1/konto", headers={"Authorization": f"Bearer {token}"}).json()["email"] is None


def test_apple_und_google_mit_geprueftem_token(stufen):
    from app.controllers.konto import pruefer
    from app.services.anmeldung import AnmeldeFehler, Identitaet

    def falsch_oder_gut(anbieter, token):
        if token.startswith("gut"):
            return Identitaet(anbieter, "000123.abc", "a@privaterelay.appleid.com")
        raise AnmeldeFehler("Signatur")
    app.dependency_overrides[pruefer] = lambda: falsch_oder_gut
    try:
        with TestClient(app) as c:
            assert c.post("/api/v1/konto/anmelden/apple", json={"id_token": "boese" * 5}).status_code == 401
            r = c.post("/api/v1/konto/anmelden/apple", json={"id_token": "gut" * 10})
            assert r.status_code == 200 and r.json()["email"] == "a@privaterelay.appleid.com"
            assert c.post("/api/v1/konto/anmelden/facebook", json={"id_token": "gut" * 10}).status_code == 404
            assert c.delete("/api/v1/konto").json() == {"email": None}  # Konto löschen (App-Store-Pflicht)
    finally:
        app.dependency_overrides.pop(pruefer, None)


def test_echtes_token_wird_abgelehnt_ohne_einrichtung():
    from app.services.anmeldung import AnmeldeFehler, pruefen
    with pytest.raises(AnmeldeFehler):
        pruefen("google", "eyJhbGciOiJSUzI1NiJ9.e30.x", [])


def test_demo_anmeldung_nicht_im_echten_betrieb(tmp_path):
    e = Einstellungen(database_url=f"sqlite:///{tmp_path / 'x.db'}", anthropic_api_key="echt", konto_pflicht=True)
    app.dependency_overrides[einstellungen] = lambda: e
    try:
        with TestClient(app) as c:
            assert c.post("/api/v1/konto/anmelden/demo", json={"id_token": "x" * 30}).status_code == 401
    finally:
        app.dependency_overrides.pop(einstellungen, None)


def test_umwandeln_braucht_konto(stufen):
    with TestClient(app, headers={"X-Geraet": "konto-test-002"}) as c:
        r = c.post("/api/v1/bauplan/anpassen", json={"graph": alte_graphen()[2], "wunsch": "breiter"})
        assert r.status_code == 401
        token = _anmelden(c)
        r = c.post("/api/v1/bauplan/anpassen", json={"graph": alte_graphen()[2], "wunsch": "breiter"},
                   headers={"Authorization": f"Bearer {token}"})
        assert r.status_code != 401, r.text  # Konto da: weiter (im Demo-Modus dann 501, kein Claude)


def test_bauplan_gesperrt_bis_freigeschaltet(stufen):
    g = alte_graphen()[2]
    with TestClient(app, headers={"X-Geraet": "konto-test-003"}) as c:
        r = c.post("/api/v1/bauplan/berechnen?mit_html=true&mit_glb=false", json={"graph": g, "bereich": PLATZ})
        j = r.json()
        assert j["gesperrt"] and j["plan"] == {} and "einkauf" not in j["bauplan"] and j["modell"]["teile"]
        assert "Freischalten" in j["html"] and j["bauplan"]["kopf"]["stunden"] > 0
        assert c.post("/api/v1/bauplan/pdf", json={"graph": g, "bereich": PLATZ}).status_code == 402
        assert c.post("/api/v1/bauplan/dxf", json={"graph": g, "bereich": PLATZ}).status_code == 402
        assert c.post("/api/v1/freischalten", json={"code": "FALSCH", "graph": g}).status_code == 404
        assert c.post("/api/v1/freischalten", json={"code": "partner", "graph": g}).json()["freigeschaltet"]
        # Größe ändern gehört zum selben Bauplan
        r = c.post("/api/v1/bauplan/berechnen?mit_glb=false", json={"graph": {**g, "ziel": [1800, 450, 804]}, "bereich": PLATZ})
        assert not r.json()["gesperrt"] and r.json()["plan"]["lines"]
        assert c.post("/api/v1/bauplan/pdf", json={"graph": g, "bereich": PLATZ}).status_code == 200
        # Freischaltung vom Gerät geht bei der Anmeldung aufs Konto über
        token = _anmelden(c)
    with TestClient(app, headers={"X-Geraet": "anderes-geraet-9", "Authorization": f"Bearer {token}"}) as c2:
        r = c2.post("/api/v1/bauplan/berechnen?mit_glb=false", json={"graph": g, "bereich": PLATZ})
        assert not r.json()["gesperrt"]


def test_ohne_schalter_alles_wie_bisher():
    with TestClient(app, headers={"X-Geraet": "konto-test-004"}) as c:
        r = c.post("/api/v1/bauplan/berechnen?mit_glb=false", json={"graph": alte_graphen()[2], "bereich": PLATZ})
        assert not r.json()["gesperrt"] and r.json()["plan"]["lines"]


def test_cors_nur_lokal():
    from fastapi.testclient import TestClient

    from app.main import create_app
    c = TestClient(create_app())
    h = {"Origin": "http://localhost:54123", "Access-Control-Request-Method": "POST",
         "Access-Control-Request-Headers": "authorization,content-type"}
    r = c.options("/api/v1/entwuerfe", headers=h)
    assert r.headers.get("access-control-allow-origin") == "http://localhost:54123"
    r = c.options("/api/v1/entwuerfe", headers={**h, "Origin": "https://boese.example"})
    assert "access-control-allow-origin" not in r.headers
