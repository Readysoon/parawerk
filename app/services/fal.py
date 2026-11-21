"""Gemeinsames für alle Modelle auf fal.ai: Aufruf, Datenschutz-Header, Ergebnis als data-URL.

Nur Modelle mit ``enterprise_status = ready`` verwenden (prüfen: ``GET https://api.fal.ai/v1/models?endpoint_id=…
&expand=enterprise_status``). Nur für diese gelten fals Zusage „kein Training mit Kundendaten“ und die DPA; Modelle
mit ``pending`` sind davon ausgenommen (Auskunft fal-Support, 20.11.2026). Stand 21.11.2026: ready sind
``fal-ai/flux-pro/v1/fill``, ``fal-ai/flux-pro/kontext``, ``fal-ai/bria/background/remove``; pending u. a.
``fal-ai/birefnet/v2``, ``fal-ai/imageutils/rembg``, ``fal-ai/imageutils/depth`` und Depth Anything v2.

Jeder Aufruf
- schickt Bilder als data-URL hin und bekommt sie mit ``sync_mode`` als data-URL zurück (nichts im fal-Verlauf),
- sagt mit ``X-Fal-Store-IO: 0``, dass fal Eingaben und Ergebnisse nicht speichern soll,
- lässt Dateien auf dem fal-CDN, falls doch welche entstehen, nach 1 Stunde löschen.
"""
from __future__ import annotations

import base64
import json

import httpx

from ..i18n import t
from .fehler import DienstFehler

URL = "https://fal.run/"
CDN_FRIST_S = 3600


def kopf(schluessel: str) -> dict[str, str]:
    return {
        "Authorization": f"Key {schluessel}",
        "Content-Type": "application/json",
        "X-Fal-Store-IO": "0",
        "X-Fal-Object-Lifecycle-Preference": json.dumps({"expiration_duration_seconds": CDN_FRIST_S}),
    }


class FalBasis:
    def __init__(self, schluessel: str, transport: httpx.AsyncBaseTransport | None = None, timeout: float = 120):
        self._kopf = kopf(schluessel)
        self._transport, self._timeout = transport, timeout

    async def _aufrufen(self, client: httpx.AsyncClient, modell: str, eingabe: dict) -> dict:
        r = await client.post(URL + modell, headers=self._kopf, json={**eingabe, "sync_mode": True})
        if r.status_code >= 400:
            raise DienstFehler(f"fal: {r.status_code} {r.text[:300]}")
        return r.json()

    @staticmethod
    async def _als_data_url(client: httpx.AsyncClient, bild: dict | None) -> str:
        """Bild-Objekt der Antwort (``{"url": …}``) → data-URL; eine echte URL wird sofort abgeholt."""
        url = (bild or {}).get("url") or ""
        if url.startswith("data:"):
            return url
        if not url:
            raise DienstFehler("fal: kein Bild in der Antwort")
        res = await client.get(url)
        if res.status_code >= 400:
            raise DienstFehler(t("fehler.nicht_abrufbar", code=res.status_code))
        typ = (bild.get("content_type") or res.headers.get("content-type", "")).split(";")[0]
        typ = typ if typ.startswith("image/") else "image/png"
        return f"data:{typ};base64," + base64.b64encode(res.content).decode()

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)
