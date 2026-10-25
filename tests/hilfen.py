"""Gemeinsame Hilfen für die API-Tests: Testbilder, ersetzte KI-Dienste, auf Aufträge warten."""
from __future__ import annotations

import base64
import io
import json
import time
from functools import lru_cache
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.services.fehler import DienstFehler

BEREICH = [2000, 1000, 1000]
REFERENZ = Path(__file__).parent / "referenz"


@lru_cache
def _alte() -> list[dict]:
    return json.loads((REFERENZ / "demo_graphen_alt.json").read_text(encoding="utf-8"))


def alte_graphen() -> list[dict]:
    """Die früheren vier Beispielgraphen. Auf ihnen beruhen die Referenzwerte der Engine-Tests (Kopie)."""
    return json.loads(json.dumps(_alte()))


GERAET = {"X-Geraet": "testgeraet-0001"}


def data_url(bild: Image.Image, fmt: str = "JPEG") -> str:
    puffer = io.BytesIO()
    bild.save(puffer, fmt)
    return f"data:image/{fmt.lower()};base64,{base64.b64encode(puffer.getvalue()).decode()}"


def foto_und_maske(w: int = 1600, h: int = 1200) -> tuple[str, str]:
    """Foto (beige) und Maske in halber Größe mit einem weißen Rechteck."""
    foto = Image.new("RGB", (w, h), (200, 190, 170))
    maske = Image.new("L", (w // 2, h // 2), 0)  # andere Größe als das Foto: der Server skaliert
    mw, mh = maske.size
    ImageDraw.Draw(maske).rectangle((mw // 8, mh // 4, mw * 5 // 8, mh * 3 // 4), fill=255)
    return data_url(foto), data_url(maske, "PNG")


FOTO, MASKE = foto_und_maske(400, 300)


class KonstrukteurAttrappe:
    demo = False

    def __init__(self):
        self.wuensche = []

    async def lesen(self, bild, bereich, demo_index=None):
        assert bild.startswith("data:image/")
        return alte_graphen()[2]

    async def pruefen(self, entwurf, modell, graph, bereich, meldungen=None):
        """Selbstkontrolle: meldet einen Mangel und benennt den Graph um, damit man die Korrektur erkennt."""
        assert entwurf.startswith("data:image/jpeg") and modell.startswith("data:image/png")
        self.pruefungen = getattr(self, "pruefungen", 0) + 1
        self.meldungen = meldungen
        if getattr(self, "pruefung_kaputt", False):
            raise DienstFehler("Claude nicht erreichbar")
        neu = json.loads(json.dumps(graph))
        neu["name"] += " (geprüft)"
        return {"passt": False, "maengel": ["Die Lehne fehlt."], "graph": neu}

    async def anpassen(self, graph, wunsch):
        self.wuensche.append(wunsch)
        graph["masse"]["breite"] += 200
        return graph

    async def bild_prompt(self, wunsch, foto, maske):
        if "offline" in wunsch:
            raise DienstFehler("Claude nicht erreichbar")
        return f"An L-shaped sofa ({wunsch}). Only this one piece of furniture."

    async def bearbeitungs_prompt(self, wunsch, anpassung, bild):
        if "offline" in anpassung:
            raise DienstFehler("Claude nicht erreichbar")
        return f"Make the backrest of the sofa {anpassung}."


class BildKIAttrappe:
    """Malt den ganzen Entwurf rot (Nachjustieren: blau); eingesetzt werden darf nur der markierte Bereich."""
    demo = False

    async def entwerfen(self, foto, maske, prompt, seeds):
        if "kaputt" in prompt:
            raise DienstFehler("Zeitüberschreitung")
        return [data_url(Image.new("RGB", (512, 384), (255, 0, 0))) for _ in seeds]

    async def bearbeiten(self, bild, anweisung, seed):
        assert bild.startswith("data:image/")
        return data_url(Image.new("RGB", (512, 384), (0, 0, 255)))


def warten(c: TestClient, start, kopf: dict | None = None) -> dict:
    """Auftrag bis zum Ende abfragen. ``start`` ist die Antwort auf den Start oder die Auftrags-ID."""
    if not isinstance(start, str):
        assert start.status_code == 202, start.text
        start = start.json()["auftrag"]
    for _ in range(300):
        stand = c.get(f"/api/v1/auftraege/{start}", headers=kopf or GERAET).json()
        if stand["status"] != "laeuft":
            return stand
        time.sleep(0.02)
    raise AssertionError("Auftrag läuft zu lange")
