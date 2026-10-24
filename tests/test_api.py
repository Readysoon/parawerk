"""API im Demo-Modus und mit ersetzten KI-Diensten: Prompts, Fehler, Startseite."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from app.services.konstrukteur import demo_graphen
from tests.hilfen import BEREICH, FOTO, GERAET, MASKE, BildKIAttrappe, KonstrukteurAttrappe, warten


@pytest.fixture
def client():
    # immer ohne Schlüssel; Kontingente großzügig, die prüft test_kostendeckel.py
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None, gratis_runden=100, ip_runden_pro_tag=100,
                                                                    gratis_nachjustieren=100)
    with TestClient(app, headers=GERAET) as c:  # ein Event-Loop für alle Anfragen, damit Aufträge weiterlaufen
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def echt(client):
    k = KonstrukteurAttrappe()
    app.dependency_overrides[konstrukteur] = lambda: k
    app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
    client.konstrukteur = k
    return client


def test_startseite(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Parawerk" in r.text and "Demo-Modus" in r.text
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/gesund").json() == {"ok": True}
    assert client.post("/api/entwuerfe", json={}).status_code in (404, 405)  # alte Aufrufe gibt es nicht mehr


def test_demo_ablauf(client):
    stand = warten(client, client.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "Daybed"}))
    assert stand["ergebnis"]["demo"] and len(stand["ergebnis"]["entwuerfe"]) == 4
    r = client.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE})
    maske_id = r.json()["maske_id"]
    entwurf = warten(client, r)["ergebnis"]["entwuerfe"][3]["id"]
    graph = warten(client, client.post("/api/v1/bauplan/lesen", json={
        "entwurf_id": entwurf, "maske_id": maske_id, "bereich": BEREICH, "demo_index": 3}))["ergebnis"]["graph"]
    assert graph["name"] == "Daybed mit Lattenkorb"
    r = client.post("/api/v1/bauplan/berechnen?mit_html=true&mit_glb=false", json={"graph": graph, "bereich": BEREICH})
    j = r.json()
    assert r.status_code == 200 and j["offene_punkte"] == 0 and "modell_glb" not in j
    assert "baubar und stabil" in j["html"] and "Einkaufsliste" in j["html"]
    assert j["modell"]["dims"] == [1750, 854, 563] and j["modell"]["teile"]
    assert "html" not in client.post("/api/v1/bauplan/berechnen", json={"graph": graph, "bereich": BEREICH}).json()
    r = client.post("/api/v1/bauplan/dxf", json={"graph": graph, "bereich": BEREICH})
    assert r.status_code == 200 and r.headers["content-type"] == "application/dxf" and r.text.endswith("EOF")


def test_ohne_schluessel(client):
    r = client.post("/api/v1/bauplan/anpassen", json={"graph": demo_graphen()[0], "wunsch": "höher"})
    assert r.status_code == 501 and "ANTHROPIC_API_KEY" in r.json()["fehler"]
    r = client.post("/api/v1/entwuerfe/nachjustieren", json={
        "foto_id": "a" * 32, "maske_id": "a" * 32, "entwurf_id": "a" * 32, "anpassung": "höher"})
    assert r.status_code == 501 and "REPLICATE_API_TOKEN" in r.json()["fehler"]


def test_fehler_sind_lesbar(client):
    r = client.post("/api/v1/bauplan/berechnen", json={"graph": {"teile": []}, "bereich": BEREICH})
    assert r.status_code == 422 and r.json() == {"fehler": "Der Bauteilgraph enthält keine Teile."}
    r = client.post("/api/v1/bauplan/berechnen", json={"graph": demo_graphen()[0], "bereich": [1, 2]})
    assert r.status_code == 422 and "bereich" in r.json()["fehler"]


def test_prompts_mit_echten_diensten(echt):
    assert echt.post("/api/v1/entwuerfe", json={"wunsch": "Bank"}).status_code == 422  # Foto und Maske fehlen
    stand = warten(echt, echt.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "Bank"}))
    assert not stand["ergebnis"]["demo"] and stand["ergebnis"]["prompt"].startswith("An L-shaped sofa (Bank)")
    stand = warten(echt, echt.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "Bank offline"}))
    assert "this exact spot of the room: Bank offline" in stand["ergebnis"]["prompt"]  # ohne Claude: wörtlich
    stand = warten(echt, echt.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "kaputt"}))
    assert stand["status"] == "fehler" and "Zeitüberschreitung" in stand["fehler"]


def test_nachjustieren_prompts(echt):
    r = echt.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE})
    ids = r.json()
    entwurf = warten(echt, r)["ergebnis"]["entwuerfe"][0]["id"]
    nj = {"foto_id": ids["foto_id"], "maske_id": ids["maske_id"], "entwurf_id": entwurf}
    stand = warten(echt, echt.post("/api/v1/entwuerfe/nachjustieren", json={**nj, "wunsch": "Sofa", "anpassung": "höher"}))
    assert stand["ergebnis"]["prompt"] == "Make the backrest of the sofa höher."
    stand = warten(echt, echt.post("/api/v1/entwuerfe/nachjustieren", json={**nj, "anpassung": "höher offline"}))
    assert stand["ergebnis"]["prompt"].startswith("Change only the newly built wooden furniture: höher offline.")
    assert echt.post("/api/v1/entwuerfe/nachjustieren", json={**nj, "anpassung": ""}).status_code == 422
