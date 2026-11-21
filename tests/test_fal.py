"""FLUX Fill und Kontext über fal: ein Aufruf je Seed, sync_mode, Datenschutz-Header; Auswahl des Anbieters."""
import asyncio
import json

import httpx

from app.config import Einstellungen
from app.controllers.abhaengigkeiten import bild_ki, tiefen_ki
from app.services.bild_ki import DemoBildKI, FalFluxFill, ReplicateFluxFill
from app.services.tiefe import DemoTiefe, ReplicateTiefe

BILD = "data:image/jpeg;base64,/9j/AA=="


def _api(aufrufe):
    def api(req: httpx.Request) -> httpx.Response:
        aufrufe.append((str(req.url), req.headers, json.loads(req.content)))
        return httpx.Response(200, json={"images": [{"url": BILD}]})
    return api


def test_entwerfen_je_seed_ein_aufruf():
    aufrufe = []
    ki = FalFluxFill("test", transport=httpx.MockTransport(_api(aufrufe)))
    bilder = asyncio.run(ki.entwerfen("data:image/jpeg;base64,AA", "data:image/png;base64,AA", "Sitzbank", [1, 2, 3, 4]))
    assert bilder == [BILD] * 4
    assert sorted(d["seed"] for _, _, d in aufrufe) == [1, 2, 3, 4]
    for url, kopf, daten in aufrufe:
        assert url == "https://fal.run/fal-ai/flux-pro/v1/fill"
        assert kopf["x-fal-store-io"] == "0" and daten["sync_mode"] is True
        assert daten["mask_url"].startswith("data:image/png") and daten["prompt"] == "Sitzbank"


def test_bearbeiten_mit_kontext():
    aufrufe = []
    ki = FalFluxFill("test", transport=httpx.MockTransport(_api(aufrufe)))
    assert asyncio.run(ki.bearbeiten(BILD, "Lehne höher", 7)) == BILD
    url, kopf, daten = aufrufe[0]
    assert url == "https://fal.run/fal-ai/flux-pro/kontext" and daten["image_url"] == BILD and daten["seed"] == 7


def _e(**werte):
    return Einstellungen(_env_file=None, **werte)


def test_anbieter_auswahl():
    assert isinstance(bild_ki(_e(fal_key="f")), FalFluxFill)
    assert isinstance(bild_ki(_e(fal_key="f", replicate_api_token="r")), FalFluxFill)  # fal hat Vorrang
    assert isinstance(bild_ki(_e(replicate_api_token="r")), ReplicateFluxFill)
    assert isinstance(bild_ki(_e(fal_key="f", replicate_api_token="r", bild_anbieter="replicate")), ReplicateFluxFill)
    assert isinstance(bild_ki(_e()), DemoBildKI)
    assert isinstance(tiefen_ki(_e(fal_key="f")), DemoTiefe)  # Tiefe nur mit Replicate
    assert isinstance(tiefen_ki(_e(fal_key="f", replicate_api_token="r")), ReplicateTiefe)
