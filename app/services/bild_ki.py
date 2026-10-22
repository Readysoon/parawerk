"""Bild-KI: malt Möbelentwürfe in den markierten Bereich eines Fotos (Inpainting mit Maske).

Austauschbar: Jeder Anbieter, der ein eigenes Foto mit Maske bearbeiten kann, lässt sich als Klasse mit
``entwerfen`` einsetzen. Die App setzt unabhängig vom Anbieter nur den markierten Ausschnitt zurück ins Foto.
"""
from __future__ import annotations

import asyncio
import base64
import re
from typing import Protocol

import httpx

from .fehler import DienstFehler

DATA_URL = re.compile(r"^data:([^;]+);base64,(.*)$", re.S)


class BildKI(Protocol):
    demo: bool

    async def entwerfen(self, foto: str, maske: str, prompt: str, seeds: list[int]) -> list[str]:
        """Foto und Maske (data-URLs, Weiß = neu malen) → ein Bild je Seed (data-URL oder URL)."""
        ...


class ReplicateFluxFill:
    """FLUX Fill Pro über Replicate."""

    demo = False
    API = "https://api.replicate.com/v1"
    MAX_DATA_URL = 250_000  # größere Dateien nimmt Replicate nicht als data-URL, sie gehen über die Files-API

    def __init__(self, token: str, model: str) -> None:
        self.token, self.model = token, model

    @property
    def _auth(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def _eingabe(self, client: httpx.AsyncClient, data_url: str, name: str) -> str:
        if len(data_url) < self.MAX_DATA_URL:
            return data_url
        m = DATA_URL.match(data_url)
        if not m:
            raise DienstFehler("Bild muss als data-URL kommen.")
        res = await client.post(f"{self.API}/files", headers=self._auth,
                                files={"content": (name, base64.b64decode(m.group(2)), m.group(1))})
        if res.status_code >= 400:
            raise DienstFehler(f"Replicate-Upload: {res.status_code} {res.text[:200]}")
        return res.json()["urls"]["get"]

    async def _warten(self, client: httpx.AsyncClient, pred: dict) -> str:
        for _ in range(90):
            if pred.get("status") in ("succeeded", "failed", "canceled"):
                break
            await asyncio.sleep(2)
            pred = (await client.get(pred["urls"]["get"], headers=self._auth)).json()
        if pred.get("status") != "succeeded":
            raise DienstFehler(f"Replicate: {pred.get('status')} {pred.get('error') or ''}")
        out = pred["output"]
        return out[0] if isinstance(out, list) else out

    async def _ein_bild(self, client: httpx.AsyncClient, foto: str, maske: str, prompt: str, seed: int) -> str:
        res = await client.post(
            f"{self.API}/models/{self.model}/predictions",
            headers={**self._auth, "Content-Type": "application/json", "Prefer": "wait=60"},
            json={"input": {"image": foto, "mask": maske, "prompt": prompt, "seed": seed, "output_format": "jpg"}},
        )
        if res.status_code >= 400:
            raise DienstFehler(f"Replicate: {res.status_code} {res.text[:300]}")
        url = await self._warten(client, res.json())
        bild = await client.get(url)
        return "data:image/jpeg;base64," + base64.b64encode(bild.content).decode()

    async def entwerfen(self, foto: str, maske: str, prompt: str, seeds: list[int]) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                f, m = await asyncio.gather(self._eingabe(client, foto, "foto.jpg"), self._eingabe(client, maske, "maske.png"))
                return list(await asyncio.gather(*(self._ein_bild(client, f, m, prompt, s) for s in seeds)))
        except httpx.HTTPError as err:
            raise DienstFehler(f"Replicate nicht erreichbar: {type(err).__name__}") from err


class DemoBildKI:
    """Ohne API-Schlüssel: vier fertige Entwürfe für das Beispielzimmer."""

    demo = True

    async def entwerfen(self, foto: str, maske: str, prompt: str, seeds: list[int]) -> list[str]:
        return [f"/static/demo/entwurf{i + 1}.jpg" for i in range(min(4, len(seeds)))]
