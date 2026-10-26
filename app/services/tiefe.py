"""Tiefen-KI: schätzt aus einem Foto, wie weit jeder Bildpunkt entfernt ist (Meter), dazu die Brennweite.

Standard ist Apples Depth Pro auf Replicate (ca. 0,2–0,4 Cent je Foto, wenige Sekunden). Den genauen Maßstab
liefert erst die Messung des Nutzers (``models/raum.py``), darum reicht ein schnelles Modell.
"""
from __future__ import annotations

import asyncio
import io
from typing import Protocol

import httpx
import numpy as np
from PIL import Image

from ..i18n import t
from ..models.raum import Tiefe, flach
from . import bildarbeit as ba
from .bild_ki import ReplicateBasis
from .fehler import DienstFehler


class TiefenKI(Protocol):
    demo: bool

    async def schaetzen(self, foto: Image.Image) -> Tiefe:
        ...


def _karte_aus_npz(daten: bytes) -> np.ndarray:
    """Tiefenkarte aus der npz-Datei des Modells: Feld „depth“, sonst das erste zweidimensionale Feld."""
    try:
        with np.load(io.BytesIO(daten), allow_pickle=False) as z:
            namen = ["depth"] + [n for n in z.files if n != "depth"]
            for n in namen:
                if n in z.files and np.squeeze(z[n]).ndim == 2:
                    return np.squeeze(z[n]).astype(np.float32)
    except (ValueError, OSError) as err:
        raise DienstFehler(t("fehler.tiefe_kaputt")) from err
    raise DienstFehler(t("fehler.tiefe_kaputt"))


class ReplicateTiefe(ReplicateBasis):
    demo = False

    def __init__(self, token: str, model: str, transport: httpx.AsyncBaseTransport | None = None,
                 schlafen=asyncio.sleep) -> None:
        super().__init__(token, transport, schlafen)
        self.model = model

    async def schaetzen(self, foto: Image.Image) -> Tiefe:
        try:
            async with httpx.AsyncClient(timeout=60, transport=self._transport) as client:
                bild = await self._eingabe(client, ba.als_data_url(ba.jpeg(foto, 90), "image/jpeg"), "foto.jpg")
                pred = await self._starten(client, {"image_path": bild}, self.model)
                aus = await self._warten(client, pred)
                if not isinstance(aus, dict) or not aus.get("npz"):
                    raise DienstFehler(t("fehler.tiefe_kaputt"))
                res = await client.get(aus["npz"])
                if res.status_code >= 400:
                    raise DienstFehler(t("fehler.nicht_abrufbar", code=res.status_code))
        except httpx.HTTPError as err:
            raise DienstFehler(t("fehler.replicate_weg", art=type(err).__name__)) from err
        karte = _karte_aus_npz(res.content)
        try:
            brennweite = float(aus.get("focal_length") or 0)
        except (TypeError, ValueError):
            brennweite = 0.0
        if not brennweite > 0:
            brennweite = 0.8 * max(foto.size)  # übliche Handy-Hauptkamera
        # Brennweite gilt für das Foto; hat die Karte eine andere Größe, umrechnen
        brennweite *= karte.shape[1] / foto.width
        return Tiefe(karte, brennweite).verkleinert()


class DemoTiefe:
    """Ohne Replicate-Schlüssel: alles gleich weit weg. Messen geht dann wie mit einem Lineal auf dem Foto."""

    demo = True

    async def schaetzen(self, foto: Image.Image) -> Tiefe:
        return flach(*foto.size)
