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
    """FLUX Fill Pro über Replicate.

    Replicate liefert je Auftrag (prediction) ein Bild. Die Aufträge werden nacheinander gestartet, weil
    Replicate neue Konten bremst (unter 5 $ Guthaben: 1 gleichzeitig, 6 pro Minute). Bei 429 wartet die App
    die angegebene Zeit und versucht es erneut. Gerechnet wird danach parallel.
    """

    demo = False
    API = "https://api.replicate.com/v1"
    MAX_DATA_URL = 250_000  # größere Dateien nimmt Replicate nicht als data-URL, sie gehen über die Files-API
    MAX_VERSUCHE = 8

    def __init__(self, token: str, model: str, transport: httpx.AsyncBaseTransport | None = None, schlafen=asyncio.sleep) -> None:
        self.token, self.model = token, model
        self._transport, self._schlafen = transport, schlafen

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

    @staticmethod
    def _wartezeit(res: httpx.Response) -> float:
        """Sekunden bis zum nächsten Versuch nach einem 429 (aus der Antwort, sonst 10)."""
        try:
            sek = float(res.json().get("retry_after"))
        except (ValueError, TypeError, AttributeError):
            try:
                sek = float(res.headers.get("retry-after", 10))
            except ValueError:
                sek = 10
        return min(max(sek, 1), 30) + 0.5

    async def _starten(self, client: httpx.AsyncClient, eingabe: dict) -> dict:
        for _ in range(self.MAX_VERSUCHE):
            res = await client.post(f"{self.API}/models/{self.model}/predictions",
                                    headers={**self._auth, "Content-Type": "application/json"}, json={"input": eingabe})
            if res.status_code == 429:
                await self._schlafen(self._wartezeit(res))
                continue
            if res.status_code >= 400:
                raise DienstFehler(f"Replicate: {res.status_code} {res.text[:300]}")
            return res.json()
        raise DienstFehler("Replicate bremst gerade zu stark (zu viele Anfragen). Bitte in einer Minute noch einmal versuchen.")

    async def _warten(self, client: httpx.AsyncClient, pred: dict) -> str:
        for _ in range(90):
            if pred.get("status") in ("succeeded", "failed", "canceled"):
                break
            await self._schlafen(2)
            res = await client.get(pred["urls"]["get"], headers=self._auth)
            if res.status_code == 429:
                await self._schlafen(self._wartezeit(res))
                continue
            pred = res.json()
        if pred.get("status") != "succeeded":
            raise DienstFehler(f"Replicate: {pred.get('status')} {pred.get('error') or ''}")
        out = pred["output"]
        return out[0] if isinstance(out, list) else out

    async def _fertigstellen(self, client: httpx.AsyncClient, pred: dict) -> str:
        url = await self._warten(client, pred)
        bild = await client.get(url)
        if bild.status_code >= 400:
            raise DienstFehler(f"Replicate: Bild nicht abrufbar ({bild.status_code})")
        return "data:image/jpeg;base64," + base64.b64encode(bild.content).decode()

    async def entwerfen(self, foto: str, maske: str, prompt: str, seeds: list[int]) -> list[str]:
        try:
            async with httpx.AsyncClient(timeout=120, transport=self._transport) as client:
                f, m = await asyncio.gather(self._eingabe(client, foto, "foto.jpg"), self._eingabe(client, maske, "maske.png"))
                auftraege = []
                for seed in seeds:  # nacheinander starten (Ratenlimit) …
                    eingabe = {"image": f, "mask": m, "prompt": prompt, "seed": seed, "output_format": "jpg"}
                    auftraege.append(await self._starten(client, eingabe))
                return list(await asyncio.gather(*(self._fertigstellen(client, p) for p in auftraege)))  # … parallel rechnen
        except httpx.HTTPError as err:
            raise DienstFehler(f"Replicate nicht erreichbar: {type(err).__name__}") from err


class DemoBildKI:
    """Ohne API-Schlüssel: vier fertige Entwürfe für das Beispielzimmer."""

    demo = True

    async def entwerfen(self, foto: str, maske: str, prompt: str, seeds: list[int]) -> list[str]:
        return [f"/static/demo/entwurf{i + 1}.jpg" for i in range(min(4, len(seeds)))]
