"""Bauteilgraph aus KI-Antworten holen und bereinigen."""
from __future__ import annotations

import pytest

from app.models.bauteilgraph import GraphFehler, bereinigen, json_aus_text

TEIL = {"id": "b", "name": "Beine", "typ": "kantholz", "rolle": "bein", "box": [0, 1, 0, 1, 0, 1], "anzahl": 4}


def test_json_aus_codeblock_und_fliesstext():
    assert json_aus_text('```json\n{"a": 1}\n```') == {"a": 1}
    assert json_aus_text('Hier ist der Graph: {"a": 2} – fertig.') == {"a": 2}
    with pytest.raises(GraphFehler):
        json_aus_text("kein json")


def test_ohne_teile():
    with pytest.raises(GraphFehler):
        bereinigen({"teile": []})


def test_box_fehlt():
    with pytest.raises(GraphFehler, match="Teil 1"):
        bereinigen({"teile": [{**TEIL, "box": [0, 1]}]})


def test_werte_werden_begrenzt():
    g = bereinigen({"masse": {"breite": -5}, "teile": [
        {**TEIL, "typ": "beton", "rolle": "deko", "box": [1.4, -0.2, 0.3, 0.3, 0, 1], "anzahl": 99, "achse": "q"},
        {**TEIL, "anzahl": 2.5},
    ]})
    t = g["teile"][0]
    assert g["masse"]["breite"] == 1500
    assert t["typ"] == "latte" and t["rolle"] == "rahmen" and t["achse"] == "x" and t["anzahl"] == 40
    assert t["box"][:2] == [0, 1] and t["box"][3] > t["box"][2]
    assert g["teile"][1]["anzahl"] == 3  # .5 wird aufgerundet
    assert g["teile"][1]["id"] == "bx"  # doppelte IDs werden eindeutig


def test_funktion_nur_mit_anker():
    g = bereinigen({"funktion": {"matratze": [900, 2000]}, "anker": {}, "teile": [TEIL]})
    assert g["funktion"] == {} and g["anker"] == {}
    g = bereinigen({"funktion": {"sitzhoehe": 450}, "anker": {"sitz_oben": 0.6}, "teile": [TEIL]})
    assert g["funktion"] == {"sitzhoehe": 450, "polster": 0} and g["anker"] == {"sitz_oben": 0.6}
