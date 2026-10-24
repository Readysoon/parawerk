"""API im Demo-Modus und mit ersetzten KI-Diensten."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from app.services.fehler import DienstFehler
from app.services.konstrukteur import demo_graphen

BEREICH = [2200, 1000, 1000]
FOTO = "data:image/jpeg;base64,AAAA"


@pytest.fixture
def client():
    # immer ohne Schlüssel; Kontingente großzügig, die prüft test_kostendeckel.py
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None, gratis_runden=100, ip_runden_pro_tag=100,
                                                                    gratis_nachjustieren=100)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_startseite(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Parawerk" in r.text and "Demo-Modus" in r.text
    assert client.get("/static/js/app.js").status_code == 200
    assert client.get("/gesund").json() == {"ok": True}


def test_demo_ablauf(client):
    r = client.post("/api/entwuerfe", json={"wunsch": "Daybed"})
    assert r.status_code == 200 and r.json()["demo"] and len(r.json()["bilder"]) == 4
    graph = client.post("/api/bauplan/lesen", json={"bereich": BEREICH, "demo_index": 3}).json()["graph"]
    assert graph["name"] == "Daybed mit Lattenkorb"
    r = client.post("/api/bauplan/berechnen", json={"graph": graph, "bereich": BEREICH})
    j = r.json()
    assert r.status_code == 200 and j["offene_punkte"] == 0
    assert "baubar und stabil" in j["html"] and "Einkaufsliste" in j["html"]
    assert j["modell"]["dims"] == [1750, 854, 563] and j["modell"]["teile"]
    r = client.post("/api/bauplan/dxf", json={"graph": graph, "bereich": BEREICH})
    assert r.status_code == 200 and r.headers["content-type"] == "application/dxf" and r.text.endswith("EOF")


def test_anpassen_ohne_schluessel(client):
    r = client.post("/api/bauplan/anpassen", json={"graph": demo_graphen()[0], "wunsch": "höher"})
    assert r.status_code == 501 and "ANTHROPIC_API_KEY" in r.json()["fehler"]


def test_fehler_sind_lesbar(client):
    r = client.post("/api/bauplan/berechnen", json={"graph": {"teile": []}, "bereich": BEREICH})
    assert r.status_code == 422 and r.json() == {"fehler": "Der Bauteilgraph enthält keine Teile."}
    r = client.post("/api/bauplan/berechnen", json={"graph": demo_graphen()[0], "bereich": [1, 2]})
    assert r.status_code == 422 and "bereich" in r.json()["fehler"]


class KonstrukteurAttrappe:
    demo = False

    def __init__(self):
        self.wuensche = []

    async def lesen(self, bild, bereich, demo_index=None):
        assert bild.startswith("data:image/")
        return demo_graphen()[2]

    async def anpassen(self, graph, wunsch):
        self.wuensche.append(wunsch)
        graph["masse"]["breite"] += 200
        return graph

    async def bild_prompt(self, wunsch, foto, maske):
        if "offline" in wunsch:
            raise DienstFehler("Claude nicht erreichbar")
        return f"An L-shaped sofa ({wunsch}). Only this one piece of furniture."

    async def bearbeitungs_prompt(self, wunsch, anpassung, bild):
        if "offline" in anpassung:
            raise DienstFehler("Claude nicht erreichbar")
        return f"Make the backrest of the sofa {anpassung}."


class BildKIAttrappe:
    demo = False

    async def bearbeiten(self, bild, anweisung, seed):
        assert bild.startswith("data:image/")
        return "data:image/png;base64,BEARBEITET"

    async def entwerfen(self, foto, maske, prompt, seeds):
        if "kaputt" in prompt:
            raise DienstFehler("Zeitüberschreitung")
        return [FOTO for _ in seeds]


def test_mit_echten_diensten(client):
    k = KonstrukteurAttrappe()
    app.dependency_overrides[konstrukteur] = lambda: k
    app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()

    assert client.post("/api/entwuerfe", json={"wunsch": "Bank"}).status_code == 400  # Foto und Maske fehlen
    r = client.post("/api/entwuerfe", json={"foto": FOTO, "maske": FOTO, "wunsch": "Bank"})
    assert r.status_code == 200 and not r.json()["demo"] and r.json()["prompt"].startswith("An L-shaped sofa (Bank)")
    r = client.post("/api/entwuerfe", json={"foto": FOTO, "maske": FOTO, "wunsch": "Bank offline"})
    assert r.status_code == 200 and "this exact spot of the room: Bank offline" in r.json()["prompt"]  # ohne Claude: wörtlich
    r = client.post("/api/entwuerfe", json={"foto": FOTO, "maske": FOTO, "wunsch": "kaputt"})
    assert r.status_code == 502 and "Zeitüberschreitung" in r.json()["fehler"]

    graph = client.post("/api/bauplan/lesen", json={"bild": FOTO, "bereich": BEREICH}).json()["graph"]
    r = client.post("/api/bauplan/anpassen", json={"graph": graph, "wunsch": "breiter"})
    assert r.status_code == 200 and k.wuensche == ["breiter"]


def test_nachjustieren(client):
    app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()
    app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
    r = client.post("/api/entwuerfe/nachjustieren", json={"bild": FOTO, "wunsch": "Sofa", "anpassung": "höher"})
    assert r.status_code == 200 and r.json() == {"prompt": "Make the backrest of the sofa höher.", "bild": "data:image/png;base64,BEARBEITET"}
    r = client.post("/api/entwuerfe/nachjustieren", json={"bild": FOTO, "anpassung": "höher offline"})
    assert r.status_code == 200 and r.json()["prompt"].startswith("Change only the newly built wooden furniture: höher offline.")
    assert client.post("/api/entwuerfe/nachjustieren", json={"bild": FOTO, "anpassung": ""}).status_code == 422


def test_nachjustieren_im_demo_modus(client):
    r = client.post("/api/entwuerfe/nachjustieren", json={"bild": FOTO, "anpassung": "höher"})
    assert r.status_code == 501 and "REPLICATE_API_TOKEN" in r.json()["fehler"]
