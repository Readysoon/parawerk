"""Anonyme Analyse: Entwürfe und Baupläne werden gespeichert, ohne Bilder, Geräte-ID oder IP."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import bild_ki, konstrukteur
from app.main import app
from tests.hilfen import BEREICH, FOTO, MASKE, BildKIAttrappe, KonstrukteurAttrappe, warten

GERAET = {"X-Geraet": "analyse-geraet-01", "fly-client-ip": "9.8.7.6"}


def test_durchgang_wird_anonym_gespeichert():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(
        _env_file=None, replicate_api_token="x", anthropic_api_key="x", admin_schluessel="geheim-123", gratis_runden=5)
    app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
    app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()
    try:
        with TestClient(app, headers=GERAET) as c:
            r = c.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "Bank aus Latten"})
            maske = r.json()["maske_id"]
            entwurf = warten(c, r, GERAET)["ergebnis"]["entwuerfe"][0]["id"]
            graph = warten(c, c.post("/api/v1/bauplan/lesen", json={"entwurf_id": entwurf, "maske_id": maske,
                                                                    "bereich": BEREICH}), GERAET)["ergebnis"]["graph"]
            c.post("/api/v1/bauplan/pdf", json={"graph": graph, "bereich": BEREICH, "entwurf_id": entwurf, "maske_id": maske})

            assert c.get("/api/v1/analyse").status_code == 404  # ohne Admin-Schlüssel nichts zu sehen
            c.get("/?schluessel=geheim-123")
            daten = c.get("/api/v1/analyse").json()
    finally:
        app.dependency_overrides.clear()
    meine = [d for d in daten if d.get("wunsch") == "Bank aus Latten" or d.get("lauf") == daten[-1]["lauf"]]
    arten = [d["art"] for d in meine]
    assert {"entwuerfe", "gelesen", "pdf"} <= set(arten)
    assert len({d["lauf"] for d in meine if d["art"] in ("entwuerfe", "gelesen", "pdf")}) == 1  # ein Durchgang
    pdf = next(d for d in meine if d["art"] == "pdf")
    assert pdf["graph"]["teile"] and pdf["teile"] > 0 and pdf["einkauf"]
    roh = json.dumps(meine)
    for verboten in ("analyse-geraet-01", "9.8.7.6", maske, entwurf, "data:image", "base64"):
        assert verboten not in roh  # keine Geräte-ID, IP, Bild-IDs oder Bilder


def test_bauplaene_rueckmeldungen_und_moebelbilder(tmp_path):
    """Jeder berechnete Bauplan und jede Rückmeldung landet in der Analyse; die gemalten Möbel als Bild ohne Zimmer."""
    from io import BytesIO

    from PIL import Image
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(
        _env_file=None, database_url=f"sqlite:///{tmp_path / 'a.db'}", replicate_api_token="x", anthropic_api_key="x",
        admin_schluessel="geheim-123", gratis_runden=5)
    app.dependency_overrides[bild_ki] = lambda: BildKIAttrappe()
    app.dependency_overrides[konstrukteur] = lambda: KonstrukteurAttrappe()
    try:
        with TestClient(app, headers=GERAET) as c:
            r = c.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE, "wunsch": "Stuhl"})
            maske = r.json()["maske_id"]
            entwurf = warten(c, r, GERAET)["ergebnis"]["entwuerfe"][0]["id"]
            graph = warten(c, c.post("/api/v1/bauplan/lesen", json={"entwurf_id": entwurf, "maske_id": maske,
                                                                    "bereich": BEREICH}), GERAET)["ergebnis"]["graph"]
            c.post("/api/v1/bauplan/berechnen?schnell=true&mit_glb=false", json={"graph": graph, "bereich": BEREICH})
            c.post("/api/v1/bauplan/berechnen?mit_glb=false", json={"graph": graph, "bereich": BEREICH,
                                                                     "entwurf_id": entwurf})
            r = c.post("/api/v1/rueckmeldung", json={"text": "Gurte halten so nicht", "graph": graph,
                                                     "entwurf_id": entwurf, "maske_id": maske})
            assert r.status_code == 200 and r.json()["danke"]
            assert c.post("/api/v1/rueckmeldung", json={"text": ""}).status_code == 422
            c.get("/?schluessel=geheim-123")
            daten = c.get("/api/v1/analyse").json()
            bilder = c.get("/api/v1/analyse/bilder").json()
            bild = Image.open(BytesIO(c.get(f"/api/v1/analyse/bild/{bilder[0]['id']}").content))
    finally:
        app.dependency_overrides.clear()
    berechnet = [d for d in daten if d["art"] == "berechnet"]
    assert len(berechnet) == 1  # die schnelle Vorschau zählt nicht
    gelesen = next(d for d in daten if d["art"] == "gelesen")
    rm = next(d for d in daten if d["art"] == "rueckmeldung")
    assert berechnet[0]["entwurf"] == gelesen["entwurf"] == rm["entwurf"] and rm["entwurf"]
    assert rm["text"] == "Gurte halten so nicht" and rm["graph"]["teile"] and rm["lauf"] == gelesen["lauf"]
    assert "statik" in berechnet[0] and berechnet[0]["teile"] > 0
    assert len(bilder) == 4 and bilder[0]["entwurf"] == gelesen["entwurf"]
    assert bild.size[0] > 0
    roh = json.dumps(daten) + json.dumps(bilder)
    for verboten in ("analyse-geraet-01", "9.8.7.6", maske, entwurf):
        assert verboten not in roh


def test_nur_moebel_ohne_zimmer():
    """Außerhalb der Markierung bleibt nichts vom Bild übrig (weiß), zugeschnitten auf die Markierung."""
    from PIL import Image, ImageDraw

    from app.services.bildarbeit import nur_moebel
    gemalt = Image.new("RGB", (400, 300), (200, 30, 30))  # „Zimmer“ und Möbel: alles rot
    maske = Image.new("L", (400, 300), 0)
    ImageDraw.Draw(maske).ellipse((100, 50, 300, 250), fill=255)
    aus = nur_moebel(gemalt, maske)
    assert abs(aus.size[0] - 200) <= 1 and abs(aus.size[1] - 200) <= 1
    assert aus.getpixel((2, 2)) == (255, 255, 255)  # Ecke außerhalb der Ellipse
    r, g, b = aus.getpixel((100, 100))
    assert r > 150 and g < 80
