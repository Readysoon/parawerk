"""Meine Projekte: nach dem Anmelde-Schritt gespeichert, je Entwurf eins, gehen beim Anmelden aufs Konto über."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import delete

from app.config import Einstellungen, einstellungen
from app.main import app
from app.models import speicher
from app.models.verbrauch import datenbank
from tests.hilfen import alte_graphen

PLATZ = [6000, 3000, 3000]


@pytest.fixture
def e(tmp_path):
    e = Einstellungen(database_url=f"sqlite:///{tmp_path / 'p.db'}")
    app.dependency_overrides[einstellungen] = lambda: e
    yield e
    app.dependency_overrides.pop(einstellungen, None)


def _entwurf(e) -> str:
    buf = io.BytesIO()
    Image.new("RGB", (1600, 1200), (180, 150, 120)).save(buf, "JPEG")
    return speicher.bild_speichern(datenbank(e.database_url), "geraet-p1", buf.getvalue(), "image/jpeg")


def _foto_und_maske(e) -> tuple[str, str]:
    db = datenbank(e.database_url)
    return (speicher.bild_speichern(db, "geraet-p1", b"FOTO-BYTES", "image/jpeg"),
            speicher.bild_speichern(db, "geraet-p1", b"MASKE-BYTES", "image/png"))


def test_projekt_speichern_oeffnen_loeschen(e):
    eid = _entwurf(e)
    fid, mid = _foto_und_maske(e)
    g = alte_graphen()[0]
    with TestClient(app, headers={"X-Geraet": "geraet-p1"}) as c:
        # ohne speichern: kein Projekt
        c.post("/api/v1/bauplan/berechnen?mit_glb=false", json={"graph": g, "bereich": PLATZ, "entwurf_id": eid})
        assert c.get("/api/v1/projekte").json()["projekte"] == []
        r = c.post("/api/v1/bauplan/berechnen?mit_glb=false",
                   json={"graph": g, "bereich": PLATZ, "entwurf_id": eid, "speichern": True,
                         "foto_id": fid, "maske_id": mid, "wunsch": "Sitzbank"})
        pid = r.json()["projekt_id"]
        # gleicher Entwurf, neue Größe: dasselbe Projekt
        r2 = c.post("/api/v1/bauplan/berechnen?mit_glb=false",
                    json={"graph": {**g, "ziel": [1500, 800, 700]}, "bereich": PLATZ, "entwurf_id": eid, "speichern": True})
        assert r2.json()["projekt_id"] == pid
        liste = c.get("/api/v1/projekte").json()["projekte"]
        assert [p["id"] for p in liste] == [pid] and liste[0]["bild_url"]
        bild = c.get(liste[0]["bild_url"])
        assert bild.status_code == 200 and Image.open(io.BytesIO(bild.content)).width <= 1200
        # Bilder nach 7 Tagen aufgeräumt: Öffnen stellt den Entwurf wieder her
        with datenbank(e.database_url).begin() as conn:
            conn.execute(delete(speicher.bilder))
        p = c.get(f"/api/v1/projekte/{pid}").json()
        assert p["graph"]["ziel"] == [1500, 800, 700] and p["entwurf"]["id"] == eid
        assert c.get(p["entwurf"]["url"]).status_code == 200
        # Wohnungsfoto und Markierung sind wieder da (zum Weiteranpassen), mit Wunsch
        assert (p["foto_id"], p["maske_id"], p["wunsch"]) == (fid, mid, "Sitzbank")
        db = datenbank(e.database_url)
        assert speicher.bild_laden(db, fid) == (b"FOTO-BYTES", "image/jpeg")
        assert speicher.bild_laden(db, mid) == (b"MASKE-BYTES", "image/png")
    # ein anderes Gerät sieht es nicht
    with TestClient(app, headers={"X-Geraet": "geraet-p2"}) as c2:
        assert c2.get("/api/v1/projekte").json()["projekte"] == []
        assert c2.get(f"/api/v1/projekte/{pid}").status_code == 404
        assert c2.delete(f"/api/v1/projekte/{pid}").status_code == 404
    with TestClient(app, headers={"X-Geraet": "geraet-p1"}) as c:
        assert c.delete(f"/api/v1/projekte/{pid}").json()["ok"]
        assert c.get("/api/v1/projekte").json()["projekte"] == []


def test_projekte_gehen_beim_anmelden_aufs_konto(tmp_path):
    e = Einstellungen(database_url=f"sqlite:///{tmp_path / 'p.db'}", konto_pflicht=False)
    app.dependency_overrides[einstellungen] = lambda: e
    try:
        eid = _entwurf(e)
        with TestClient(app, headers={"X-Geraet": "geraet-p1"}) as c:
            c.post("/api/v1/bauplan/berechnen?mit_glb=false",
                   json={"graph": alte_graphen()[1], "bereich": PLATZ, "entwurf_id": eid, "speichern": True})
            token = c.post("/api/v1/konto/anmelden/demo", json={"id_token": "projekt-nutzer-xxxxxxxxx"}).json()["token"]
            kopf = {"Authorization": f"Bearer {token}"}
            assert len(c.get("/api/v1/projekte", headers=kopf).json()["projekte"]) == 1
            c.cookies.clear()
            assert c.get("/api/v1/projekte").json()["projekte"] == []  # Gerät ohne Anmeldung: weg
            c.delete("/api/v1/konto", headers=kopf)
        with TestClient(app, headers={"X-Geraet": "geraet-p1"}) as c:
            token = c.post("/api/v1/konto/anmelden/demo", json={"id_token": "projekt-nutzer-xxxxxxxxx"}).json()["token"]
            assert c.get("/api/v1/projekte", headers={"Authorization": f"Bearer {token}"}).json()["projekte"] == []
    finally:
        app.dependency_overrides.pop(einstellungen, None)
