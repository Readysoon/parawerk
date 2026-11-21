"""Freistellen: nur das gemalte Möbel aus einem Entwurf ausschneiden (transparenter Hintergrund).

Zwischen Entwurf und 3D-Modell: Die Lerndaten bekommen ein sauberes Möbelbild ohne Wand und Boden, und die
3D-Erzeugung (Tripo & Co.) braucht ein freigestelltes Objekt als Eingabe.

Ablauf (``bildarbeit.moebel_ausschnitt`` / ``freigestellt``): Ausschnitt um die Markierung → Bria (fal.ai)
liefert die Deckkraft → mit der Markierung verknüpft, damit nichts vom echten Zimmer außerhalb mitkommt.
Ohne ``FAL_KEY`` (oder im Demo-Modus) gibt es keinen Freisteller; dann bleibt es beim groben Ausschnitt über die
Markierung (``bildarbeit.nur_moebel``).
"""
from __future__ import annotations

from typing import Protocol

import httpx
from PIL import Image

from . import bildarbeit as ba
from .fal import FalBasis
from .fehler import DienstFehler


class Freisteller(Protocol):
    async def deckkraft(self, bild: Image.Image) -> Image.Image:
        """Deckkraft (L, 0 = Hintergrund, 255 = Objekt) in der Größe von ``bild``."""
        ...


class FalBria(FalBasis):
    """Bria „Background Remove“ auf fal.ai („Enterprise Ready“, siehe ``services/fal.py``; BiRefNet ist dort nur
    „pending“ und fällt nicht unter fals Zusage „kein Training“). Bria liefert ein PNG mit durchsichtigem Hintergrund;
    dessen Alphakanal ist die Deckkraft."""

    def __init__(self, schluessel: str, modell: str = "fal-ai/bria/background/remove",
                 transport: httpx.AsyncBaseTransport | None = None):
        super().__init__(schluessel, transport, timeout=60)
        self.modell = modell

    async def deckkraft(self, bild: Image.Image) -> Image.Image:
        eingabe = ba.als_data_url(ba.jpeg(bild.convert("RGB"), 92), "image/jpeg")
        try:
            async with self._client() as c:
                aus = await self._aufrufen(c, self.modell, {"image_url": eingabe})
                frei = ba.aus_data_url(await self._als_data_url(c, aus.get("image")))
        except httpx.HTTPError as err:
            raise DienstFehler(f"fal: {type(err).__name__}") from err
        if frei.mode in ("RGBA", "LA") or "transparency" in frei.info:
            maske = frei.convert("RGBA").getchannel("A")
        else:  # ohne Alphakanal (sollte nicht vorkommen): nichts freigestellt
            maske = Image.new("L", frei.size, 255)
        return maske.resize(bild.size, Image.LANCZOS)
