"""Claude-Anbindung mit simulierter API: Bauteilgraph kommt als Structured Output."""
from __future__ import annotations

import asyncio
import json

import httpx
import pytest

import app.services.konstrukteur as modul
from app.services.fehler import DienstFehler
from app.services.konstrukteur import ClaudeKonstrukteur
from tests.hilfen import alte_graphen as demo_graphen

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


def _ohne_unerlaubtes(schema) -> bool:
    """Structured Outputs: Objekte brauchen additionalProperties false, Zahl- und Längengrenzen gibt es nicht."""
    if isinstance(schema, dict):
        if schema.get("type") == "object" and schema.get("additionalProperties") is not False:
            return False
        if {"minimum", "maximum", "minItems", "maxItems", "minLength", "maxLength"} & schema.keys():
            return False
        return all(_ohne_unerlaubtes(v) for v in schema.values())
    if isinstance(schema, list):
        return all(_ohne_unerlaubtes(v) for v in schema)
    return True


def test_lesen_als_structured_output(claude):
    graph = json.loads(json.dumps(demo_graphen()[3]))  # Kopie, die Demo-Graphen sind zwischengespeichert
    graph["teile"][0]["rolle"] = graph["teile"][0]["rolle"].upper()  # Enum-Werte können anders geschrieben kommen
    claude["antwort"] = {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(graph)}]}
    g = asyncio.run(ClaudeKonstrukteur("k", "claude-sonnet-5-5").lesen(FOTO, [2000, 1000, 1000]))
    assert g["name"] == "Daybed mit Lattenkorb" and len(g["teile"]) == len(graph["teile"])
    assert g["teile"][0]["rolle"] == demo_graphen()[3]["teile"][0]["rolle"]
    anfrage = claude["anfragen"][0]
    fmt = anfrage["output_config"]["format"]
    assert fmt["type"] == "json_schema" and fmt["schema"]["required"][-1] == "teile" and _ohne_unerlaubtes(fmt["schema"])
    assert "tools" not in anfrage and "tool_choice" not in anfrage
    assert [c["type"] for c in anfrage["messages"][0]["content"]] == ["image", "text"]


def test_rueckfall_auf_text_mit_kommentar(claude):
    text = json.dumps(demo_graphen()[0], ensure_ascii=False).replace('"teile":', '// Teile folgen\n"teile":', 1)
    claude["antwort"] = {"stop_reason": "end_turn", "content": [{"type": "text", "text": text}]}
    g = asyncio.run(ClaudeKonstrukteur("k", "m").anpassen(demo_graphen()[0], "höher"))
    assert g["name"] == "Palettensofa"


def test_abgeschnittene_antwort(claude):
    claude["antwort"] = {"stop_reason": "max_tokens", "content": [{"type": "text", "text": '{"name": "Ba'}]}
    with pytest.raises(DienstFehler, match="zu lang"):
        asyncio.run(ClaudeKonstrukteur("k", "m").lesen(FOTO, [2000, 1000, 1000]))
