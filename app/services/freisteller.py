"""Freistellen: nur das gemalte Möbel aus einem Entwurf ausschneiden (transparenter Hintergrund).

Zwischen Entwurf und 3D-Modell: Die Lerndaten bekommen ein sauberes Möbelbild ohne Wand und Boden, und die
3D-Erzeugung (Tripo & Co.) braucht ein freigestelltes Objekt als Eingabe.

Ablauf (``bildarbeit.moebel_ausschnitt`` / ``freigestellt``): Ausschnitt um die Markierung → BiRefNet (fal.ai)
liefert die Deckkraft → mit der Markierung verknüpft, damit nichts vom echten Zimmer außerhalb mitkommt.
Ohne ``FAL_KEY`` (oder im Demo-Modus) gibt es keinen Freisteller; dann bleibt es beim groben Ausschnitt über die
Markierung (``bildarbeit.nur_moebel``).
"""
from __future__ import annotations

from typing import Protocol

import httpx
from PIL import Image

from . import bildarbeit as ba
from .fehler import DienstFehler


class Freisteller(Protocol):
    async def deckkraft(self, bild: Image.Image) -> Image.Image:
        """Deckkraft (L, 0 = Hintergrund, 255 = Objekt) in der Größe von ``bild``."""
        ...


class FalBiRefNet:
    URL = "https://fal.run/"

    def __init__(self, schluessel: str, modell: str = "fal-ai/birefnet/v2"):
        self._kopf = {"Authorization": f"Key {schluessel}", "Content-Type": "application/json"}
        self.modell = modell

    async def deckkraft(self, bild: Image.Image) -> Image.Image:
        eingabe = ba.als_data_url(ba.jpeg(bild.convert("RGB"), 92), "image/jpeg")
        daten = {"image_url": eingabe, "model": "General Use (Heavy)", "operating_resolution": "1024x1024",
                 "output_format": "png", "mask_only": True, "sync_mode": True}
        async with httpx.AsyncClient(timeout=60) as c:
            r = await c.post(self.URL + self.modell, headers=self._kopf, json=daten)
            if r.status_code >= 400:
                raise DienstFehler(f"fal: {r.status_code} {r.text[:300]}")
            url = (r.json().get("image") or {}).get("url") or ""
            if url.startswith("data:"):
                maske = ba.aus_data_url(url)
            elif url:
                maske = ba.aus_bytes((await c.get(url)).content)
            else:
                raise DienstFehler("fal: kein Bild in der Antwort")
        return maske.convert("L").resize(bild.size, Image.LANCZOS)
