"""Konstrukteur: liest aus einem Entwurfsbild den Bauteilgraph und ändert ihn auf Wunsch.

``ClaudeKonstrukteur`` nutzt die Claude-API, ``DemoKonstrukteur`` liefert ohne Schlüssel die Graphen der
vier Beispielentwürfe.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

import httpx

from ..i18n import name, t
from ..models.bauteilgraph import JSON_SCHEMA, bereinigen, json_aus_text
from .fehler import DienstFehler, NichtVerfuegbar
from .prompts import (KONTEXT_REGELN, anpass_prompt, bearbeitung_anweisung, bearbeitung_prompt, bildprompt_anweisung,
                      inpaint_prompt, inpaint_prompt_aus, lese_prompt)


class Konstrukteur(Protocol):
    demo: bool

    async def lesen(self, bild: str | None, bereich: list[float], demo_index: int | None = None) -> dict: ...

    async def anpassen(self, graph: dict, wunsch: str) -> dict: ...

    async def bild_prompt(self, wunsch: str, foto: str | None, maske: str | None) -> str: ...

    async def bearbeitungs_prompt(self, wunsch: str, anpassung: str, bild: str) -> str: ...


DATA_URL = re.compile(r"^data:(image/[a-z]+);base64,(.*)$", re.S)


class ClaudeKonstrukteur:
    demo = False
    URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str, model: str, timeout: float = 120) -> None:
        self.api_key, self.model, self.timeout = api_key, model, timeout

    async def _senden(self, text: str, bild: str | list[str] | None, max_tokens: int, schema: dict | None = None) -> dict:
        content: list[dict] = []
        for b in ([bild] if isinstance(bild, str) else bild or []):
            m = DATA_URL.match(b)
            if not m:
                raise DienstFehler(t("fehler.data_url"))
            content.append({"type": "image", "source": {"type": "base64", "media_type": m.group(1), "data": m.group(2)}})
        content.append({"type": "text", "text": text})
        body: dict = {"model": self.model, "max_tokens": max_tokens, "messages": [{"role": "user", "content": content}]}
        if schema:  # Structured Outputs: Antwort ist JSON nach diesem Schema
            body["output_config"] = {"format": {"type": "json_schema", "schema": schema}}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    self.URL,
                    headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                    json=body,
                )
        except httpx.HTTPError as err:
            raise DienstFehler(t("fehler.claude_weg", art=type(err).__name__)) from err
        if res.status_code >= 400:
            raise DienstFehler(f"Claude-API: {res.status_code} {res.text[:300]}")
        j = res.json()
        if j.get("stop_reason") == "max_tokens":
            raise DienstFehler(t("fehler.zu_lang"))
        if j.get("stop_reason") == "refusal":
            raise DienstFehler(t("fehler.abgelehnt"))
        return j

    async def _fragen(self, text: str, bild: str | list[str] | None = None, max_tokens: int = 4000) -> str:
        j = await self._senden(text, bild, max_tokens)
        return "\n".join(c["text"] for c in j.get("content", []) if c.get("type") == "text")

    async def _graph(self, text: str, bild: str | None = None) -> dict:
        """Bauteilgraph als Structured Output: Claude antwortet mit JSON nach ``JSON_SCHEMA``."""
        j = await self._senden(text, bild, 8000, JSON_SCHEMA)
        texte = "\n".join(c.get("text", "") for c in j.get("content", []) if c.get("type") == "text")
        return bereinigen(json_aus_text(texte))  # verträgt zur Sicherheit auch Codeblöcke und Kommentare

    async def lesen(self, bild: str | None, bereich: list[float], demo_index: int | None = None) -> dict:
        return await self._graph(lese_prompt(bereich), bild)

    async def anpassen(self, graph: dict, wunsch: str) -> dict:
        return await self._graph(anpass_prompt(graph, wunsch))

    async def bild_prompt(self, wunsch: str, foto: str | None, maske: str | None) -> str:
        """Wunsch → präziser englischer Prompt für die Bild-KI, mit Blick auf Foto und Maske."""
        bilder = [b for b in (foto, maske) if b]
        text = (await self._fragen(bildprompt_anweisung(wunsch), bilder, max_tokens=400)).strip().strip('"')
        if not text:
            raise DienstFehler(t("fehler.keine_beschreibung"))
        return inpaint_prompt_aus(text)

    async def bearbeitungs_prompt(self, wunsch: str, anpassung: str, bild: str) -> str:
        """Nachjustieren: Wunsch → englische Bearbeitungsanweisung, mit Blick auf den Entwurf."""
        text = (await self._fragen(bearbeitung_anweisung(wunsch, anpassung), [bild], max_tokens=300)).strip().strip('"')
        if not text:
            raise DienstFehler(t("fehler.keine_anweisung"))
        return f"{text} {KONTEXT_REGELN}"


@lru_cache
def demo_graphen() -> list[dict]:
    return json.loads((Path(__file__).parent / "demo_graphen.json").read_text(encoding="utf-8"))


class DemoKonstrukteur:
    """Ohne API-Schlüssel: Graphen der vier Beispielentwürfe (vorab von Claude aus den Bildern gelesen)."""

    demo = True

    async def lesen(self, bild: str | None, bereich: list[float], demo_index: int | None = None) -> dict:
        graphen = demo_graphen()
        i = demo_index if isinstance(demo_index, int) and 0 <= demo_index < len(graphen) else 0
        graph = json.loads(json.dumps(graphen[i]))
        graph["name"] = name(graph["name"])
        for teil in graph["teile"]:
            teil["name"] = name(teil["name"])
        return graph

    async def anpassen(self, graph: dict, wunsch: str) -> dict:
        raise NichtVerfuegbar(t("fehler.anpassen_demo"))

    async def bild_prompt(self, wunsch: str, foto: str | None, maske: str | None) -> str:
        return inpaint_prompt(wunsch)

    async def bearbeitungs_prompt(self, wunsch: str, anpassung: str, bild: str) -> str:
        return bearbeitung_prompt(anpassung)
