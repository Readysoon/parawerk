"""Kostendeckel: Gratis-Kontingent je Gerät, Limit je IP, Tagesbudget, Erstattung bei Fehlern, Admin-Schlüssel."""
from __future__ import annotations

import secrets
from contextlib import ExitStack

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from app.models.verbrauch import _url
from tests.hilfen import BEREICH, FOTO, MASKE, BildKIAttrappe, KonstrukteurAttrappe, warten

ENTWURF = {"foto": FOTO, "maske": MASKE, "wunsch": "Bank"}


@pytest.fixture
def einrichten():
    """Ersetzte KI-Dienste wie mit Schlüsseln; die Einstellungen gibt der Test vor. Liefert eine Fabrik für Geräte."""
    with ExitStack() as stapel:
        def setzen(**werte):
            app.dependency_overrides[einstellungen] = lambda: Einstellungen(
                _env_file=None, replicate_api_token="x", anthropic_api_key="x", **werte)
            app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
            app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()

            def geraet(ip: str = "1.2.3.4") -> TestClient:
                """Neues Gerät (eigene ID) hinter der angegebenen IP."""
                kopf = {"fly-client-ip": ip, "X-Geraet": "test-" + secrets.token_hex(8)}
                return stapel.enter_context(TestClient(app, headers=kopf))
            return geraet
        yield setzen
    app.dependency_overrides.clear()


def runde(c: TestClient, **extra) -> int:
    """Eine Runde Entwürfe; bei Erfolg bis zum Ende abwarten. Gibt den Status des Starts zurück."""
    r = c.post("/api/v1/entwuerfe", json={**ENTWURF, **extra})
    if r.status_code == 202:
        warten(c, r, dict(c.headers))
    return r.status_code


def test_eine_gratis_runde_je_geraet(einrichten):
    c = einrichten()()
    assert c.get("/api/v1/kontingent").json() == {"runden": 1, "nachjustieren": 2}
    assert runde(c) == 202
    assert c.get("/api/v1/kontingent").json()["runden"] == 0
    r = c.post("/api/v1/entwuerfe", json=ENTWURF)
    assert r.status_code == 402 and "Gratis-Runde" in r.json()["fehler"]


def test_fehlgeschlagene_runde_wird_erstattet(einrichten):
    c = einrichten()()
    stand = warten(c, c.post("/api/v1/entwuerfe", json={**ENTWURF, "wunsch": "kaputt"}), dict(c.headers))
    assert stand["status"] == "fehler"
    assert c.get("/api/v1/kontingent").json()["runden"] == 1
    assert runde(c) == 202


def test_limit_je_ip(einrichten):
    geraet = einrichten(ip_runden_pro_tag=3)
    assert [runde(geraet()) for _ in range(3)] == [202] * 3  # neue Geräte-IDs helfen nur bis zum IP-Limit
    r = geraet().post("/api/v1/entwuerfe", json=ENTWURF)
    assert r.status_code == 429 and "Netzwerk" in r.json()["fehler"]
    assert runde(geraet("5.6.7.8")) == 202


def test_nachjustieren_gezaehlt(einrichten):
    c = einrichten()()
    r = c.post("/api/v1/entwuerfe", json=ENTWURF)
    ids = r.json()
    entwurf = warten(c, r, dict(c.headers))["ergebnis"]["entwuerfe"][0]["id"]
    nj = {"foto_id": ids["foto_id"], "maske_id": ids["maske_id"], "entwurf_id": entwurf, "anpassung": "höher"}
    codes = []
    for _ in range(3):
        r = c.post("/api/v1/entwuerfe/nachjustieren", json=nj)
        codes.append(r.status_code)
        if r.status_code == 202:
            warten(c, r, dict(c.headers))
    assert codes == [202, 202, 402]
    assert c.get("/api/v1/kontingent").json() == {"runden": 0, "nachjustieren": 0}


def test_tagesbudget_gilt_fuer_alle(einrichten):
    geraet = einrichten(tagesbudget_usd=0.3, admin_schluessel="geheim-123")
    assert runde(geraet("1.1.1.1")) == 202
    admin = geraet("2.2.2.2")
    admin.get("/?schluessel=geheim-123")
    r = admin.post("/api/v1/entwuerfe", json=ENTWURF)
    assert r.status_code == 503 and "Budget" in r.json()["fehler"]


def test_admin_ohne_kontingent(einrichten):
    c = einrichten(admin_schluessel="geheim-123")()
    r = c.get("/?schluessel=falsch", follow_redirects=False)
    assert r.status_code == 303 and "admin" not in r.cookies
    r = c.get("/?schluessel=geheim-123", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/" and r.cookies.get("admin")
    assert c.get("/api/v1/kontingent").json() == {"runden": None, "nachjustieren": None}
    assert [runde(c) for _ in range(4)] == [202] * 4


def test_lesen_und_anpassen_je_tag(einrichten):
    geraet = einrichten(lesen_pro_tag=2, anpassen_pro_tag=1, gratis_runden=5)
    c = geraet()
    r = c.post("/api/v1/entwuerfe", json=ENTWURF)
    maske = r.json()["maske_id"]
    entwurf = warten(c, r, dict(c.headers))["ergebnis"]["entwuerfe"][0]["id"]
    lesen = {"entwurf_id": entwurf, "maske_id": maske, "bereich": BEREICH}
    codes, graph = [], None
    for _ in range(3):
        r = c.post("/api/v1/bauplan/lesen", json=lesen)
        codes.append(r.status_code)
        if r.status_code == 202:
            graph = warten(c, r, dict(c.headers))["ergebnis"]["graph"]
    assert codes == [202, 202, 429]
    codes = []
    for _ in range(2):
        r = c.post("/api/v1/bauplan/anpassen", json={"graph": graph, "wunsch": "breiter"})
        codes.append(r.status_code)
        if r.status_code == 202:
            warten(c, r, dict(c.headers))
    assert codes == [202, 429]


def test_demo_modus_ohne_grenzen():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None)
    try:
        with TestClient(app, headers={"X-Geraet": "demo-geraet-01"}) as c:
            assert c.get("/api/v1/kontingent").json() == {"runden": None, "nachjustieren": None}
            assert [runde(c) for _ in range(3)] == [202] * 3
    finally:
        app.dependency_overrides.clear()


def test_browser_bekommt_geraete_cookie():
    with TestClient(app) as c:
        assert c.get("/").cookies.get("geraet")


def test_postgres_url_von_fly():
    assert _url("postgres://u:p@host:5432/db") == "postgresql+psycopg://u:p@host:5432/db"
    assert _url("sqlite:///x.db") == "sqlite:///x.db"
