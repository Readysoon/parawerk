"""Replicate-Anbindung mit simulierter API (kein Netz)."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.services.bild_ki import ReplicateFluxFill
from app.services.fehler import DienstFehler

FOTO = "data:image/jpeg;base64,AAAA"


class FalschesReplicate:
    """Bremst wie Replicate bei wenig Guthaben: jeder zweite Start bekommt 429."""

    def __init__(self, drosseln=True, immer_429=False):
        self.drosseln, self.immer_429 = drosseln, immer_429
        self.starts, self.abgelehnt, self.seeds = 0, 0, []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if req.method == "POST" and req.url.path.endswith("/predictions"):
            self.starts += 1
            if self.immer_429 or (self.drosseln and self.starts % 2 == 0):
                self.abgelehnt += 1
                return httpx.Response(429, json={"detail": "Request was throttled.", "status": 429, "retry_after": 10})
            seed = json.loads(req.content)["input"]["seed"]
            self.seeds.append(seed)
            return httpx.Response(201, json={"status": "starting", "urls": {"get": f"https://api.replicate.com/v1/predictions/{seed}"}})
        if req.url.path.startswith("/v1/predictions/"):
            seed = req.url.path.rsplit("/", 1)[1]
            return httpx.Response(200, json={"status": "succeeded", "output": [f"https://bilder.test/{seed}.jpg"]})
        if req.url.host == "bilder.test":
            return httpx.Response(200, content=b"jpg")
        return httpx.Response(404)


def _ki(api, pausen):
    async def schlafen(s):
        pausen.append(s)
    return ReplicateFluxFill("r8_test", "black-forest-labs/flux-fill-pro", transport=httpx.MockTransport(api), schlafen=schlafen)


def test_wartet_bei_429_und_liefert_alle_bilder():
    api, pausen = FalschesReplicate(), []
    bilder = asyncio.run(_ki(api, pausen).entwerfen(FOTO, FOTO, "Bank", [1, 2, 3, 4]))
    assert len(bilder) == 4 and all(b.startswith("data:image/jpeg;base64,") for b in bilder)
    assert api.seeds == [1, 2, 3, 4]  # jeder Seed genau einmal gestartet
    assert api.abgelehnt == 3 and pausen.count(10.5) == 3  # retry_after + 0,5 s


def test_gibt_nach_zu_vielen_429_auf():
    api, pausen = FalschesReplicate(immer_429=True), []
    with pytest.raises(DienstFehler, match="bremst"):
        asyncio.run(_ki(api, pausen).entwerfen(FOTO, FOTO, "Bank", [1]))
    assert api.starts == ReplicateFluxFill.MAX_VERSUCHE
