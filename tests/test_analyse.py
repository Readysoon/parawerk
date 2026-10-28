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
