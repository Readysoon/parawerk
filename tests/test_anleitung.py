"""Bauanleitung: Buchstaben je Teil, Schritte mit „Das brauchst du“, Kopf mit Zeit und Kosten."""
from __future__ import annotations

from collections import Counter

import pytest

from app.models.bauteilgraph import bereinigen
from app.models.engine import berechnen
from app.models.engine.anleitung import anleitung
from app.models.engine.grundlagen import ext
from app.views.praesentation import bauplan_ansicht, modell_3d
from tests.hilfen import alte_graphen

PLATZ = [6000, 3000, 3000]


@pytest.mark.parametrize("i", range(4))
def test_jedes_teil_genau_einmal_und_gleiche_teile_gleicher_buchstabe(i):
    g = bereinigen(alte_graphen()[i])
    e = berechnen(g, PLATZ)
    a = anleitung(e.members, e.joints, e.plan, e.dims)
    ids = [x for s in a["schritte"] for x in s["ids"]]
    assert Counter(ids) == Counter(m.id for m in e.members)  # jedes Teil kommt in genau einem Schritt vor
    nach_b: dict[str, set] = {}
    for m in e.members:
        if m.typ != "gurt":
            nach_b.setdefault(a["buchstaben"][m.id], set()).add(
                tuple(sorted(round(ext(m, k)) for k in (0, 1, 2))))
    assert all(len(v) == 1 for v in nach_b.values())  # ein Buchstabe = ein Maß
    assert sum(x["n"] for x in a["teileliste"]) == sum(1 for m in e.members if m.typ != "gurt")


def test_schrauben_der_schritte_passen_zur_einkaufsliste():
    g = bereinigen(alte_graphen()[2])
    e = berechnen(g, PLATZ)
    a = anleitung(e.members, e.joints, e.plan, e.dims)
    je_art: Counter = Counter()
    for s in a["schritte"]:
        for x in s["schrauben"]:
            je_art[x["text"]] += x["n"]
    for h in e.plan["hardware"]:
        if h["text"] in je_art:  # Einkauf = Bedarf + 10 % Reserve, aufgerundet
            assert h["n"] == -(-je_art[h["text"]] * 11 // 10)


def test_kopf_und_ansicht():
    g = bereinigen(alte_graphen()[2])
    e = berechnen(g, PLATZ)
    v = bauplan_ansicht(e, g, PLATZ)
    k = v["kopf"]
    assert 1 <= k["stufe"] <= 5 and k["stunden"] >= 1 and k["personen"] in (1, 2)
    assert k["preis"] and 50 < k["preis"] < 1000 and "€" in k["preis_text"]
    assert v["werkzeug"] and v["schritte"][-1]["ids"] == []  # zuletzt: schleifen und ölen
    assert any(p["b"] for g_ in v["zuschnitt"] if g_["art"] == "stab" for st in g_["stangen"] for p in st["stuecke"])
    assert all("b" in t for t in modell_3d(e)["teile"] if not t.get("gurt"))


def test_armlehne_liegt_auf_dem_bein():
    import json
    from pathlib import Path

    from app.models.engine.reparatur import spannweite
    from app.models.engine.setzen import kontakte
    g = json.loads((Path(__file__).parents[1] / "app/services/demo_graphen.json").read_text(encoding="utf-8"))[0]
    e = berechnen(bereinigen(g), PLATZ)
    J = kontakte(e.members)
    for m in (m for m in e.members if m.part == "ar"):
        si = spannweite(m, J)
        assert si["supported"] and not si["worst"].get("cant"), si  # kein freies Ende mehr
        assert any(j["ax"] == 2 and (j["a"].rolle == "bein" or j["b"].rolle == "bein") and m in (j["a"], j["b"])
                   for j in J)
    assert e.offene_punkte == 0


def test_schrauben_lang_genug_und_auf_der_kontaktflaeche():
    from app.models.engine import schrauben as sch
    e = berechnen(bereinigen(alte_graphen()[2]), PLATZ)
    n = 0
    for j in e.joints:
        v = sch.verbindung(j)
        if not v:
            continue
        n += 1
        dicke = ext(v["durch"], v["ax"])
        assert v["l"] <= dicke + ext(v["ins"], v["ax"]) - 5  # geht nicht hinten wieder raus
        for s in v["stellen"]:
            for a in (0, 1, 2):
                if a != v["ax"]:
                    assert max(v["durch"].min[a], v["ins"].min[a]) - 0.01 <= s["p"][a] <= min(v["durch"].max[a], v["ins"].max[a]) + 0.01
    assert n > 10
    assert all(l.get("preis") for l in e.plan["lines"]) and all(h.get("preis") for h in e.plan["hardware"])
