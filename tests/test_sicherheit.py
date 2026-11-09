"""Sicherheitsregeln: Hochbetten (EN 747) werden gesperrt, hohe Regale bekommen eine Kippsicherung."""
from __future__ import annotations

import gzip
import json
from pathlib import Path

from app.models.engine import berechnen, sicherheit
from app.models.engine.grundlagen import Bauteil


def _teil(rolle, z0, z1):
    return Bauteil(min=[0, 0, z0], max=[2000, 900, z1], long=0, rolle=rolle)


def test_hochbett_ab_600_mm():
    bein = Bauteil(min=[0, 0, 0], max=[60, 60, 1600], long=2, rolle="bein")
    assert sicherheit.ist_hochbett([bein, _teil("lattenrost", 1180, 1200)], {"kategorie": "bett"}) == 1200
    assert sicherheit.ist_hochbett([bein, _teil("lattenrost", 380, 400)], {"kategorie": "bett"}) is None
    assert sicherheit.ist_hochbett([bein, _teil("sitzflaeche", 700, 720)], {"kategorie": "bank"}) is None


def test_hochbett_nur_warnung(monkeypatch):
    """Kein Sperren: der Plan entsteht, die Prüfung warnt deutlich (offener Punkt)."""
    from app.models.engine import __init__ as eng  # noqa: F401
    import app.models.engine as engine
    monkeypatch.setattr(engine.sicherheit, "ist_hochbett", lambda ms, g: 1320)
    faelle = json.loads(gzip.open(Path(__file__).parent / "referenz" / "engine_faelle.json.gz", "rt").read())
    f = faelle[0]
    e = berechnen(f["graph"], f["bereich"], f["sortiment"])
    assert e.plan["lines"]
    w = [c for c in e.checks if "EN 747" in c["t"]]
    assert w and w[0]["ok"] is False and "1320" in w[0]["t"]


def test_hohes_regal_bekommt_kippsicherung():
    faelle = json.loads(gzip.open(Path(__file__).parent / "referenz" / "engine_faelle.json.gz", "rt").read())
    f = next(x for x in faelle if x["name"] == "fuzz39_blindtest2")
    e = berechnen(f["graph"], f["bereich"], f["sortiment"])
    assert any("Kippsicherung" in h["text"] for h in e.plan["hardware"])
    assert e.plan["steps"][-1]["key"] == "montage.kippsicherung"
    assert any("Kippsicherung" in c["t"] for c in e.checks)
    from app.models.engine.anleitung import anleitung
    a = anleitung(e.members, e.joints, e.plan, e.dims)
    assert "Kippsicherung" in a["schritte"][-1]["t"]


def test_niedriges_regal_und_wandregal_ohne():
    boden = Bauteil(min=[0, 0, 300], max=[800, 300, 318], long=0, rolle="regalboden")
    bein = Bauteil(min=[0, 0, 0], max=[30, 30, 500], long=2, rolle="bein")
    assert not sicherheit.braucht_kippsicherung([boden, bein], {"kategorie": "regal"})
    hoch = Bauteil(min=[0, 0, 0], max=[30, 30, 1800], long=2, rolle="bein")
    wand = Bauteil(min=[0, 280, 1500], max=[800, 300, 1560], long=0, rolle="wandleiste")
    assert sicherheit.braucht_kippsicherung([boden, hoch], {"kategorie": "regal"})
    assert not sicherheit.braucht_kippsicherung([boden, hoch, wand], {"kategorie": "regal"})


def test_bett_mit_vier_fuessen_steht():
    """Claude schrieb bei 4 Füßen achse "z" (hochkant gemeint): Füße kommen in die Ecken und tragen den Rahmen."""
    from app.models.bauteilgraph import bereinigen
    g = json.loads((Path(__file__).parent / "referenz" / "bett_fuesse_hochkant.json").read_text(encoding="utf-8"))
    e = berechnen(bereinigen(g), [1800, 900, 900])
    fuesse = [m for m in e.members if m.rolle == "bein"]
    assert len(fuesse) == 4
    assert all(m.max[2] - m.min[2] > m.max[0] - m.min[0] for m in fuesse)  # stehen senkrecht
    ecken = {(m.min[0] < e.dims[0] / 2, m.min[1] < e.dims[1] / 2) for m in fuesse}
    assert len(ecken) == 4
    falsch = [c["t"] for c in e.checks if c["ok"] is False and "Bereich" not in c["t"]]
    assert not falsch, falsch
    # Rahmen bündig: kein Balken steht über die Außenkante
    rahmen = [m for m in e.members if m.part.startswith("rahmen")]
    assert max(m.max[0] for m in rahmen) == max(m.max[0] for m in fuesse)
