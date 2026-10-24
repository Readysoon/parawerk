"""App-API v1: ganzer Ablauf über Aufträge, Bildarbeit am Server, Bauplan als JSON, 3D als glb."""
from __future__ import annotations

import base64
import io
import json
import struct
import time

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from app.services import bildarbeit as ba
from app.services.fehler import DienstFehler
from tests.test_api import KonstrukteurAttrappe

BEREICH = [2000, 1000, 1000]
GERAET = {"X-Geraet": "testgeraet-0001"}


def data_url(bild: Image.Image, fmt: str = "JPEG") -> str:
    puffer = io.BytesIO()
    bild.save(puffer, fmt)
    return f"data:image/{fmt.lower()};base64,{base64.b64encode(puffer.getvalue()).decode()}"


def foto_und_maske(w: int = 1600, h: int = 1200) -> tuple[str, str]:
    foto = Image.new("RGB", (w, h), (200, 190, 170))
    maske = Image.new("L", (w // 2, h // 2), 0)  # andere Größe als das Foto: der Server skaliert
    ImageDraw.Draw(maske).rectangle((100, 150, 500, 450), fill=255)
    return data_url(foto), data_url(maske, "PNG")


class BildKI:
    """Malt den ganzen Entwurf rot; eingesetzt werden darf davon nur der markierte Bereich."""
    demo = False

    async def entwerfen(self, foto, maske, prompt, seeds):
        if "kaputt" in prompt:
            raise DienstFehler("Zeitüberschreitung")
        return [data_url(Image.new("RGB", (512, 384), (255, 0, 0))) for _ in seeds]

    async def bearbeiten(self, bild, anweisung, seed):
        return data_url(Image.new("RGB", (512, 384), (0, 0, 255)))


def warten(c: TestClient, aid: str) -> dict:
    for _ in range(200):
        stand = c.get(f"/api/v1/auftraege/{aid}", headers=GERAET).json()
        if stand["status"] != "laeuft":
            return stand
        time.sleep(0.02)
    raise AssertionError("Auftrag läuft zu lange")


@pytest.fixture
def echt():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None, replicate_api_token="x",
                                                                    anthropic_api_key="x")
    app.dependency_overrides[bild_ki] = lambda: BildKI()
    app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()
    with TestClient(app) as c:  # ein Event-Loop für alle Anfragen, damit Aufträge weiterlaufen
        yield c
    app.dependency_overrides.clear()


def test_ganzer_ablauf(echt):
    c = echt
    foto, maske = foto_und_maske()
    r = c.post("/api/v1/entwuerfe", json={"foto": foto, "maske": maske, "wunsch": "Bank"}, headers=GERAET)
    assert r.status_code == 202
    ids = r.json()
    stand = warten(c, ids["auftrag"])
    assert stand["status"] == "fertig", stand
    entwuerfe = stand["ergebnis"]["entwuerfe"]
    assert len(entwuerfe) == 4 and stand["ergebnis"]["prompt"].startswith("An L-shaped sofa")

    # Entwurf ist auf 1024 px verkleinert, rot nur im markierten Bereich, außen das Foto
    bild = Image.open(io.BytesIO(c.get(entwuerfe[0]["url"]).content)).convert("RGB")
    assert bild.size == (1024, 768)
    assert bild.getpixel((380, 380))[0] > 240 and bild.getpixel((380, 380))[1] < 30
    assert bild.getpixel((20, 20)) == pytest.approx((200, 190, 170), abs=4)

    # Kontingent: die eine Gratis-Runde ist weg
    assert c.get("/api/v1/kontingent", headers=GERAET).json() == {"runden": 0, "nachjustieren": 2}
    r = c.post("/api/v1/entwuerfe", json={"foto_id": ids["foto_id"], "maske_id": ids["maske_id"]}, headers=GERAET)
    assert r.status_code == 402

    # Nachjustieren: blau statt rot, wieder nur im Bereich
    r = c.post("/api/v1/entwuerfe/nachjustieren", headers=GERAET, json={
        "foto_id": ids["foto_id"], "maske_id": ids["maske_id"], "entwurf_id": entwuerfe[0]["id"], "anpassung": "blau"})
    neu = warten(c, r.json()["auftrag"])["ergebnis"]["entwurf"]
    px = Image.open(io.BytesIO(c.get(neu["url"]).content)).convert("RGB").getpixel((380, 380))
    assert px[2] > 240 and px[0] < 30

    # Lesen und Berechnen
    r = c.post("/api/v1/bauplan/lesen", headers=GERAET,
               json={"entwurf_id": entwuerfe[1]["id"], "maske_id": ids["maske_id"], "bereich": BEREICH})
    graph = warten(c, r.json()["auftrag"])["ergebnis"]["graph"]
    r = c.post("/api/v1/bauplan/berechnen", json={"graph": graph, "bereich": BEREICH}, headers={**GERAET, "X-Sprache": "en"})
    plan = r.json()
    assert r.status_code == 200 and plan["bauplan"]["pruefungen"] and plan["bauplan"]["einkauf"]
    assert plan["bauplan"]["pruefungen"][0]["status"] in ("OK", "CHECK", "NOTE")
    glb = c.get(plan["modell_glb"])
    assert glb.headers["content-type"] == "model/gltf-binary"
    pruefe_glb(glb.content, len(plan["modell"]["teile"]))

    # Anpassen
    r = c.post("/api/v1/bauplan/anpassen", json={"graph": graph, "wunsch": "breiter"}, headers=GERAET)
    assert warten(c, r.json()["auftrag"])["ergebnis"]["graph"]["masse"]["breite"] == graph["masse"]["breite"] + 200


def pruefe_glb(daten: bytes, teile: int) -> None:
    magic, version, laenge = struct.unpack_from("<III", daten)
    assert magic == 0x46546C67 and version == 2 and laenge == len(daten)
    n, art = struct.unpack_from("<II", daten, 12)
    assert art == 0x4E4F534A
    gltf = json.loads(daten[20:20 + n])
    quader = sum(a["count"] for a in gltf["accessors"] if a["type"] == "SCALAR") // 36
    assert quader >= teile and gltf["buffers"][0]["byteLength"] <= len(daten)


def test_fehler_erstattet_und_lesbar(echt):
    foto, maske = foto_und_maske()
    r = echt.post("/api/v1/entwuerfe", json={"foto": foto, "maske": maske, "wunsch": "kaputt"}, headers=GERAET)
    stand = warten(echt, r.json()["auftrag"])
    assert stand["status"] == "fehler" and "Zeitüberschreitung" in stand["fehler"]
    assert echt.get("/api/v1/kontingent", headers=GERAET).json()["runden"] == 1


def test_auftrag_nur_fuer_eigenes_geraet(echt):
    foto, maske = foto_und_maske()
    aid = echt.post("/api/v1/entwuerfe", json={"foto": foto, "maske": maske}, headers=GERAET).json()["auftrag"]
    warten(echt, aid)
    assert echt.get(f"/api/v1/auftraege/{aid}", headers={"X-Geraet": "anderes-geraet-1"}).status_code == 404


def test_ohne_markierung(echt):
    foto, _ = foto_und_maske()
    leer = data_url(Image.new("L", (100, 100), 0), "PNG")
    r = echt.post("/api/v1/entwuerfe", json={"foto": foto, "maske": leer}, headers=GERAET)
    assert r.status_code == 400 and "markiert" in r.json()["fehler"]
    assert echt.post("/api/v1/entwuerfe", json={"foto": foto}, headers=GERAET).status_code == 422
    assert echt.get("/api/v1/bilder/" + "0" * 32).status_code == 404


def test_demo_modus():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None)
    try:
        with TestClient(app) as c:
            foto, maske = foto_und_maske()
            ids = c.post("/api/v1/entwuerfe", json={"foto": foto, "maske": maske}, headers=GERAET).json()
            stand = warten(c, ids["auftrag"])
            assert stand["ergebnis"]["demo"] and len(stand["ergebnis"]["entwuerfe"]) == 4
            r = c.post("/api/v1/bauplan/lesen", headers=GERAET, json={
                "entwurf_id": stand["ergebnis"]["entwuerfe"][3]["id"], "maske_id": ids["maske_id"], "bereich": BEREICH,
                "demo_index": 3})
            assert warten(c, r.json()["auftrag"])["ergebnis"]["graph"]["name"] == "Daybed mit Lattenkorb"
            assert c.post("/api/v1/bauplan/anpassen", json={"graph": {"teile": [{}]}, "wunsch": "x"}).status_code == 501
    finally:
        app.dependency_overrides.clear()


def test_transparente_maske():
    """Maske aus einer Mal-App: transparent mit deckendem Strich statt schwarz-weiß."""
    m = Image.new("RGBA", (200, 100), (0, 0, 0, 0))
    ImageDraw.Draw(m).rectangle((50, 20, 150, 80), fill=(255, 200, 0, 255))
    grau = ba.maske_vorbereiten(m, (400, 200))
    assert ba.rahmen(grau) == pytest.approx((100, 40, 302, 162), abs=3)
