"""Foto hochladen, Tiefe schätzen, Raummaße aus einer Messung (API und Replicate-Anbindung)."""
from __future__ import annotations

import asyncio
import io
import json
import secrets

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Einstellungen, einstellungen
from app.controllers.abhaengigkeiten import tiefen_ki
from app.main import app
from app.services.fehler import DienstFehler
from app.services.tiefe import ReplicateTiefe
from tests.hilfen import data_url, warten
from tests.test_raum import F, H, W, _messung_rueckwand, zimmer

TIEFE, MASKE_BOOL, BILDPUNKT = zimmer()
FOTO = data_url(Image.new("RGB", (W, H), (200, 190, 170)))
MASKE = data_url(Image.fromarray(MASKE_BOOL.astype(np.uint8) * 255), "PNG")
MESSUNG = _messung_rueckwand(BILDPUNKT)
MESSUNG_JSON = {"a": list(MESSUNG.a), "b": list(MESSUNG.b), "mm": MESSUNG.mm}


class TiefenAttrappe:
    """Liefert die Tiefenkarte des gerechneten Zimmers; ``kaputt`` simuliert einen Ausfall."""
    demo = False

    def __init__(self, kaputt: bool = False):
        self.kaputt, self.aufrufe = kaputt, 0

    async def schaetzen(self, foto):
        self.aufrufe += 1
        if self.kaputt:
            raise DienstFehler("Replicate nicht erreichbar")
        return TIEFE


@pytest.fixture
def client():
    """Mit Replicate-Schlüssel (sonst Demo) und ersetzter Tiefen-KI. Liefert (Client, Attrappe, Einstellungen setzen)."""
    attrappe = TiefenAttrappe()
    werte = {}
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None, replicate_api_token="x", **werte)
    app.dependency_overrides[tiefen_ki] = lambda: attrappe
    with TestClient(app, headers={"X-Geraet": "mess-" + secrets.token_hex(6)}) as c:
        yield c, attrappe, werte
    app.dependency_overrides.clear()


def _hochladen(c: TestClient) -> dict:
    r = c.post("/api/v1/fotos", json={"foto": FOTO})
    foto_id = r.json()["foto_id"]
    stand = warten(c, r, dict(c.headers))
    assert stand["status"] == "fertig", stand
    return {"foto_id": foto_id, **stand["ergebnis"]}


def test_foto_hochladen_und_messen(client):
    c, attrappe, _ = client
    j = _hochladen(c)
    assert j["flach"] is False and attrappe.aufrufe == 1
    r = c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": MASKE, "messungen": [MESSUNG_JSON]})
    assert r.status_code == 200, r.text
    m = r.json()
    assert m["bereich"][0] == pytest.approx(1800, rel=0.04)
    assert m["bereich"][1] == pytest.approx(800, rel=0.08)
    assert m["bereich"][2] == pytest.approx(900, rel=0.04)
    assert m["nachmessen"] is False
    # das hochgeladene Foto gilt direkt für die Entwürfe (kein zweites Hochladen)
    assert c.get(f"/api/v1/bilder/{j['foto_id']}").headers["content-type"] == "image/jpeg"


def test_zwei_messungen_passen_nicht(client):
    c, _, _ = client
    j = _hochladen(c)
    falsch = {**MESSUNG_JSON, "mm": 2600}
    m = c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": MASKE, "messungen": [MESSUNG_JSON, falsch]}).json()
    assert m["nachmessen"] is True and m["abweichung"] > 0.2
    assert any("nachmessen" in h for h in m["hinweise"])


def test_tiefe_kaputt_dann_flach_und_erstattet(client):
    c, attrappe, _ = client
    attrappe.kaputt = True
    j = _hochladen(c)
    assert j["flach"] is True
    m = c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": MASKE, "messungen": [MESSUNG_JSON]},
               headers={"X-Sprache": "en"}).json()
    assert m["bereich"][1] is None and any("depth AI" in h for h in m["hinweise"])


def test_limit_je_tag_dann_flach(client):
    c, attrappe, werte = client
    werte["fotos_pro_tag"] = 1
    assert _hochladen(c)["flach"] is False
    assert _hochladen(c)["flach"] is True  # Messen geht trotzdem, nur ohne Tiefen-KI
    assert attrappe.aufrufe == 1


def test_masse_fehler(client):
    c, _, _ = client
    j = _hochladen(c)
    leer = data_url(Image.new("L", (W, H), 0), "PNG")
    assert c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": leer, "messungen": [MESSUNG_JSON]}).status_code == 400
    assert c.post("/api/v1/masse", json={"tiefe_id": j["foto_id"], "maske": MASKE, "messungen": [MESSUNG_JSON]}).status_code == 404
    zu_weit = {**MESSUNG_JSON, "a": [1.5, 0.2]}
    assert c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": MASKE, "messungen": [zu_weit]}).status_code == 422
    assert c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": MASKE, "messungen": []}).status_code == 422


def test_demo_misst_flach():
    app.dependency_overrides[einstellungen] = lambda: Einstellungen(_env_file=None)
    try:
        with TestClient(app, headers={"X-Geraet": "demo-mess-01"}) as c:
            j = _hochladen(c)
            assert j["flach"] is True
            maske = np.zeros((H, W), np.uint8)
            maske[100:200, 50:250] = 255  # 200 px breit, 100 px hoch
            m = c.post("/api/v1/masse", json={"tiefe_id": j["tiefe_id"], "maske": data_url(Image.fromarray(maske), "PNG"),
                                              "messungen": [{"a": [0.0, 0.5], "b": [0.5, 0.5], "mm": 1000}]}).json()
            assert m["bereich"][0] == pytest.approx(1000, rel=0.03) and m["bereich"][2] == pytest.approx(500, rel=0.03)
    finally:
        app.dependency_overrides.clear()


# ---------- Anbindung an Replicate (Depth Pro) ----------

def _npz(**felder) -> bytes:
    puffer = io.BytesIO()
    np.savez(puffer, **felder)
    return puffer.getvalue()


def test_replicate_depth_pro():
    anfragen = []
    karte = TIEFE.karte * 2  # andere Werte, gleiche Größe wie die Karte

    def api(req: httpx.Request) -> httpx.Response:
        anfragen.append(req)
        if req.url.path == "/v1/predictions":
            return httpx.Response(201, json={"status": "starting", "urls": {"get": "https://api.replicate.com/v1/predictions/p1"}})
        if req.url.path == "/v1/predictions/p1":
            return httpx.Response(200, json={"status": "succeeded", "output": {
                "npz": "https://replicate.delivery/x/tiefe.npz", "color_map": "https://replicate.delivery/x/c.png",
                "focal_length": F * 2}})
        if req.url.path.endswith("tiefe.npz"):
            return httpx.Response(200, content=_npz(depth=karte[None], focallength_px=np.float32(F * 2)))
        return httpx.Response(404)

    ki = ReplicateTiefe("r8_test", "ibrahimpenekli/depth-pro:abc123", transport=httpx.MockTransport(api),
                        schlafen=lambda s: asyncio.sleep(0))
    foto = Image.new("RGB", (W * 2, H * 2))  # Foto doppelt so groß wie die Karte: Brennweite wird umgerechnet
    t = asyncio.run(ki.schaetzen(foto))
    start = json.loads(anfragen[0].content)
    assert start["version"] == "abc123" and start["input"]["image_path"].startswith("data:image/jpeg")
    assert t.karte.shape == (H, W) and t.brennweite == pytest.approx(F) and not t.flach


def test_replicate_ohne_npz():
    def api(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/v1/predictions":
            return httpx.Response(201, json={"status": "succeeded", "output": {"color_map": "x"}, "urls": {"get": "x"}})
        return httpx.Response(404)

    ki = ReplicateTiefe("r8_test", "a/b:v", transport=httpx.MockTransport(api))
    with pytest.raises(DienstFehler):
        asyncio.run(ki.schaetzen(Image.new("RGB", (64, 48))))
