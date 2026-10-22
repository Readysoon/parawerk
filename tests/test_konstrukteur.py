"""Claude-Anbindung mit simulierter API: Bauteilgraph kommt über Tool Use."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import app.services.konstrukteur as modul
from app.services.fehler import DienstFehler
from app.services.konstrukteur import ClaudeKonstrukteur, demo_graphen

FOTO = "data:image/jpeg;base64,AAAA"


@pytest.fixture
def claude(monkeypatch):
    """Ersetzt die Claude-API; ``antwort`` legt fest, was zurückkommt, ``anfragen`` sammelt die Anfragen."""
    zustand = {"antwort": None, "anfragen": []}
    echt = httpx.AsyncClient

    def api(req: httpx.Request) -> httpx.Response:
        zustand["anfragen"].append(json.loads(req.content))
        return httpx.Response(200, json=zustand["antwort"])

    monkeypatch.setattr(modul.httpx, "AsyncClient", lambda **kw: echt(transport=httpx.MockTransport(api), **kw))
    return zustand


def test_lesen_ueber_tool_use(claude):
    claude["antwort"] = {"stop_reason": "tool_use", "content": [
        {"type": "text", "text": "Hier der Graph."},
        {"type": "tool_use", "name": "bauteilgraph", "input": demo_graphen()[3]},
    ]}
    g = asyncio.run(ClaudeKonstrukteur("k", "claude-sonnet-5-5").lesen(FOTO, [2000, 1000, 1000]))
    assert g["name"] == "Daybed mit Lattenkorb" and len(g["teile"]) == len(demo_graphen()[3]["teile"])
    anfrage = claude["anfragen"][0]
    assert anfrage["tool_choice"] == {"type": "tool", "name": "bauteilgraph"}
    assert anfrage["tools"][0]["input_schema"]["required"][-1] == "teile"
    assert [c["type"] for c in anfrage["messages"][0]["content"]] == ["image", "text"]


def test_rueckfall_auf_text_mit_kommentar(claude):
    text = json.dumps(demo_graphen()[0], ensure_ascii=False).replace('"teile":', '// Teile folgen\n"teile":', 1)
    claude["antwort"] = {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}
    g = asyncio.run(ClaudeKonstrukteur("k", "m").anpassen(demo_graphen()[0], "höher"))
    assert g["name"] == "Palettensofa"


def test_abgeschnittene_antwort(claude):
    claude["antwort"] = {"stop_reason": "max_tokens", "content": [{"type": "tool_use", "name": "bauteilgraph", "input": {}}]}
    with pytest.raises(DienstFehler, match="zu lang"):
        asyncio.run(ClaudeKonstrukteur("k", "m").lesen(FOTO, [2000, 1000, 1000]))
