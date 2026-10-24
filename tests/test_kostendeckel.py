"""Kostendeckel: Gratis-Kontingent je Gerät, Limit je IP, Tagesbudget, Erstattung bei Fehlern, Admin-Schlüssel."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from app.models.verbrauch import _url
from tests.test_api import FOTO, BildKIAttrappe, KonstrukteurAttrappe

ENTWURF = {"foto": FOTO, "maske": FOTO, "wunsch": "Bank"}
NJ = {"bild": FOTO, "wunsch": "Sofa", "anpassung": "höher"}


@pytest.fixture
def einrichten():
    """Echte (ersetzte) KI-Dienste; die Einstellungen gibt der Test vor."""
    def setzen(**werte):
        app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None, replicate_api_token="x", **werte)
        app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
        app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()
    yield setzen
    app.dependency_overrides.clear()


def geraet(ip: str = "1.2.3.4") -> TestClient:
    """Neuer Browser (eigene Cookies) hinter der angegebenen IP."""
    c = TestClient(app, headers={"fly-client-ip": ip})
    assert c.get("/").cookies.get("geraet")
    return c


def test_eine_gratis_runde_je_geraet(einrichten):
    einrichten()
    c = geraet()
    assert c.get("/api/kontingent").json() == {"runden": 1, "nachjustieren": 2}
    assert c.post("/api/entwuerfe", json=ENTWURF).status_code == 200
    assert c.get("/api/kontingent").json()["runden"] == 0
    r = c.post("/api/entwuerfe", json=ENTWURF)
    assert r.status_code == 402 and "Gratis-Runde" in r.json()["fehler"]


def test_fehlgeschlagene_runde_wird_erstattet(einrichten):
    einrichten()
    c = geraet()
    assert c.post("/api/entwuerfe", json={**ENTWURF, "wunsch": "kaputt"}).status_code == 502
    assert c.get("/api/kontingent").json()["runden"] == 1
    assert c.post("/api/entwuerfe", json=ENTWURF).status_code == 200


def test_limit_je_ip(einrichten):
    einrichten(ip_runden_pro_tag=3)
    for _ in range(3):  # Cookies löschen hilft nur bis zum IP-Limit
        assert geraet().post("/api/entwuerfe", json=ENTWURF).status_code == 200
    r = geraet().post("/api/entwuerfe", json=ENTWURF)
    assert r.status_code == 429 and "Netzwerk" in r.json()["fehler"]
    assert geraet("5.6.7.8").post("/api/entwuerfe", json=ENTWURF).status_code == 200


def test_nachjustieren_gezaehlt(einrichten):
    einrichten()
    c = geraet()
    assert [c.post("/api/entwuerfe/nachjustieren", json=NJ).status_code for _ in range(3)] == [200, 200, 402]
    assert c.get("/api/kontingent").json() == {"runden": 1, "nachjustieren": 0}


def test_tagesbudget_gilt_fuer_alle(einrichten):
    einrichten(tagesbudget_usd=0.3, admin_schluessel="geheim-123")
    assert geraet("1.1.1.1").post("/api/entwuerfe", json=ENTWURF).status_code == 200
    admin = geraet("2.2.2.2")
    admin.get("/?schluessel=geheim-123")
    r = admin.post("/api/entwuerfe", json=ENTWURF)
    assert r.status_code == 503 and "Budget" in r.json()["fehler"]


def test_admin_ohne_kontingent(einrichten):
    einrichten(admin_schluessel="geheim-123")
    c = geraet()
    r = c.get("/?schluessel=falsch", follow_redirects=False)
    assert r.status_code == 303 and "admin" not in r.cookies
    r = c.get("/?schluessel=geheim-123", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/" and r.cookies.get("admin")
    assert c.get("/api/kontingent").json() == {"runden": None, "nachjustieren": None}
    assert [c.post("/api/entwuerfe", json=ENTWURF).status_code for _ in range(5)] == [200] * 5


def test_lesen_und_anpassen_je_tag(einrichten):
    einrichten(lesen_pro_tag=2, anpassen_pro_tag=1)
    c = geraet()
    lesen = {"bild": FOTO, "bereich": [2000, 1000, 1000]}
    assert [c.post("/api/bauplan/lesen", json=lesen).status_code for _ in range(3)] == [200, 200, 429]
    graph = geraet("9.9.9.9").post("/api/bauplan/lesen", json=lesen).json()["graph"]
    assert [c.post("/api/bauplan/anpassen", json={"graph": graph, "wunsch": "breiter"}).status_code
            for _ in range(2)] == [200, 429]


def test_demo_modus_ohne_grenzen():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None)
    try:
        c = geraet()
        assert c.get("/api/kontingent").json() == {"runden": None, "nachjustieren": None}
        assert [c.post("/api/entwuerfe", json={"wunsch": "x"}).status_code for _ in range(3)] == [200] * 3
    finally:
        app.dependency_overrides.clear()


def test_postgres_url_von_fly():
    assert _url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert _url("sqlite:///x.db") == "sqlite:///x.db"
