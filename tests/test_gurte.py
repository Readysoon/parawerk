"""Sitz mit elastischen Polstergurten statt Holzlatten: weicher Sitz, Gurte von Zarge zu Zarge, Zug in der Statik."""
from __future__ import annotations

import json
from pathlib import Path

from app.models.bauteilgraph import bereinigen
from app.models.engine import berechnen
from app.models.engine.gurte import anzahl, umstellen, zuschnitt
from app.views.praesentation import modell_3d
from tests.hilfen import alte_graphen

PLATZ = [6000, 3000, 3000]
DEMO = json.loads((Path(__file__).parents[1] / "app/services/demo_graphen.json").read_text(encoding="utf-8"))


def _mit_gurten(g: dict) -> dict:
    return {**bereinigen(g), "sitz": "gurte"}


def test_bereinigen_behaelt_sitz():
    assert bereinigen({**DEMO[0], "sitz": "gurte"})["sitz"] == "gurte"
    assert "sitz" not in bereinigen({**DEMO[0], "sitz": "watte"})


def test_rechnen_von_hand():
    assert anzahl(1000) == 13  # 50 mm Gurt + 30 mm Lücke
    assert anzahl(60) == 2
    assert zuschnitt(400) == 400 * 0.9 + 80


def test_matratze_behaelt_lattenrost():
    bett = alte_graphen()[1]  # Bett mit Matratze
    assert all(t["rolle"] != "gurt" for t in umstellen(bereinigen(bett))["teile"])


def test_gartenbank_mit_gurten():
    g = _mit_gurten(DEMO[0])
    e = berechnen(g, PLATZ)
    gurte = [m for m in e.members if m.typ == "gurt"]
    assert len(gurte) >= 4 and e.offene_punkte == 0, [c["t"] for c in e.checks if c["ok"] is False]
    assert not any("lag nirgends auf" in r for r in e.repairs)  # Gurte laufen von Zarge zu Zarge
    # Gurte liegen auf Holz und ziehen an den Zargen
    assert any(n.art == "zug" or "zug" in n.werte for n in e.fc["statik"].nachweise)
    assert e.fc["statik"].schlechtester.ausnutzung <= 1
    # Bauplan: Gurtband, Klammern, Schaum, eigener Montageschritt; kein Gurt im Zuschnitt
    texte = " ".join(z["text"] for z in e.plan["lines"] + e.plan["hardware"])
    assert "Polstergurt" in texte and "Tackerklammern" in texte and "Polsterschaum" in texte
    assert any("Polstergurte" in s["t"] for s in e.plan["steps"])
    assert not any(i["id"].startswith("sl") for cg in e.plan["cut_groups"] if cg["kind"] == "stab"
                   for b in cg["bins"] for i in b["items"])
    assert e.soft and e.graph.get("sitz") == "gurte"
    teile = modell_3d(e)["teile"]
    assert sum(1 for t in teile if t.get("gurt")) == len(gurte)


def test_gurte_sparen_holz():
    daybed = alte_graphen()[3]  # Lattenkorb: Latten brauchen einen Mittelsteg, Gurte nicht
    latten, gurte = berechnen(bereinigen(daybed), PLATZ), berechnen(_mit_gurten(daybed), PLATZ)

    def holz(e):
        return sum((m.max[0] - m.min[0]) * (m.max[1] - m.min[1]) * (m.max[2] - m.min[2]) for m in e.members
                   if m.typ != "gurt")
    assert holz(gurte) < holz(latten)
    assert gurte.offene_punkte == 0


def test_api_dxf_und_ar():
    from fastapi.testclient import TestClient

    from app.main import app
    g = _mit_gurten(DEMO[0])
    with TestClient(app, headers={"X-Geraet": "gurte-test-01"}) as c:
        r = c.post("/api/v1/bauplan/berechnen?mit_glb=true", json={"graph": g, "bereich": PLATZ})
        assert r.status_code == 200, r.text
        assert any(t.get("gurt") for t in r.json()["modell"]["teile"])
        dxf = c.post("/api/v1/bauplan/dxf", json={"graph": g, "bereich": PLATZ})
        assert dxf.status_code == 200 and "POLSTERGURT" not in dxf.text.upper()


def test_stuhl_gurte_von_vorne_nach_hinten_auf_geschlossenem_rahmen():
    """Echter Stuhl aus einer Lesung: Gurte laufen von vorne nach hinten und liegen an beiden Enden auf einer Zarge,
    seitlich ist ebenfalls je eine Zarge (geschlossener Rahmen); Zargen stehen symmetrisch zwischen den Beinen."""
    import json
    from pathlib import Path

    from app.models.engine import berechnen
    g = json.loads((Path(__file__).parent / "referenz" / "stuhl_lattenlehne.json").read_text())
    g["sitz"] = "gurte"
    e = berechnen(g)
    gurte = [m for m in e.members if m.typ == "gurt"]
    assert gurte and all(m.long == 1 for m in gurte)
    z0 = min(m.min[2] for m in gurte)
    zargen = [m for m in e.members if m.typ == "kantholz" and m.long != 2 and abs(m.max[2] - z0) <= 1.5]
    vorne = min(m.min[1] for m in gurte)
    hinten = max(m.max[1] for m in gurte)
    assert any(m.long == 0 and m.min[1] <= vorne + 1 < m.max[1] for m in zargen)  # unter den vorderen Enden
    assert any(m.long == 0 and m.min[1] < hinten - 1 <= m.max[1] for m in zargen)  # unter den hinteren Enden
    links = min(m.min[0] for m in gurte)
    rechts = max(m.max[0] for m in gurte)
    assert any(m.long == 1 and m.max[0] <= links + 1 for m in zargen)
    assert any(m.long == 1 and m.min[0] >= rechts - 1 for m in zargen)
    seiten = sorted((m for m in e.members if m.part == "zarge"), key=lambda m: m.min[0])
    breite = e.dims[0]
    assert abs(seiten[0].min[0] - (breite - seiten[1].max[0])) <= 1  # symmetrisch
    assert e.offene_punkte == 0
