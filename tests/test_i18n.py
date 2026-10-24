"""Zweisprachigkeit: Kataloge vollständig, Sprache aus URL, Cookie und Browser, englische Ausgabe ohne deutsche Reste."""
import re
import string

import pytest
from fastapi.testclient import TestClient

from app.i18n import KATALOG, aus_header, holz, in_sprache, t
from app.main import app
from app.services.konstrukteur import demo_graphen
from tests.hilfen import FOTO, GERAET, MASKE, warten

BEREICH = [1800, 900, 900]


def _platzhalter(text: str) -> set[str]:
    return {f[1] for f in string.Formatter().parse(text) if f[1]}


def test_kataloge_gleich_aufgebaut():
    de, en = KATALOG["de"], KATALOG["en"]
    assert not [k for k in de if k not in en]
    assert not [k for k in de if _platzhalter(de[k]) != _platzhalter(en[k])]


def test_sprache_bestimmen():
    assert aus_header("en-US,en;q=0.9,de;q=0.8") == "en"
    assert aus_header("fr-FR,de;q=0.5") == "de"
    assert aus_header(None) == "de"
    with in_sprache("en"):
        assert t("bp.ok") == "buildable and stable" and holz("Latte 24×44 gehobelt") == "Planed batten 24×44"
    assert t("bp.ok") == "baubar und stabil"


def test_seite_folgt_browser_und_umschalter():
    c = TestClient(app)
    assert '<html lang="de"' in c.get("/").text
    assert '<html lang="en"' in c.get("/", headers={"accept-language": "en-GB"}).text
    r = c.get("/?sprache=en", headers={"accept-language": "de"})
    assert '<html lang="en"' in r.text and "sprache=en" in r.headers["set-cookie"]
    assert '<html lang="en"' in c.get("/", headers={"accept-language": "de"}).text  # Cookie gewinnt


@pytest.mark.parametrize("i", range(4))
def test_bauplan_englisch(i):
    with TestClient(app, cookies={"sprache": "en"}, headers=GERAET) as c:
        r = c.post("/api/v1/entwuerfe", json={"foto": FOTO, "maske": MASKE})
        maske = r.json()["maske_id"]
        entwurf = warten(c, r)["ergebnis"]["entwuerfe"][i]["id"]
        graph = warten(c, c.post("/api/v1/bauplan/lesen", json={
            "entwurf_id": entwurf, "maske_id": maske, "bereich": BEREICH, "demo_index": i}))["ergebnis"]["graph"]
        assert not re.search(r"[äöüß]", graph["name"] + "".join(teil["name"] for teil in graph["teile"]))
        j = c.post("/api/v1/bauplan/berechnen?mit_html=true", json={"graph": graph, "bereich": BEREICH}).json()
    text = re.sub(r"<[^>]+>", " ", re.sub(r'<pre class="graph">.*?</pre>', "", j["html"], flags=re.S))
    assert "Shopping list" in text and "Cut plan" in text
    for wort in ("Einkaufsliste", "Stange", "Prüfung", "Latte", "Leimholz", "Rahmenholz", "Holzschraube", "Teile"):
        assert wort not in text


def test_fehler_englisch():
    c = TestClient(app, headers={"x-sprache": "en", **GERAET})
    assert c.post("/api/v1/bauplan/berechnen", json={"graph": {"teile": []}, "bereich": BEREICH}).json() == {
        "fehler": "The part graph has no parts."}
    assert c.post("/api/v1/bauplan/berechnen", json={}).json()["fehler"].startswith("Invalid input:")
    r = c.post("/api/v1/bauplan/anpassen", json={"graph": demo_graphen()[0], "wunsch": "wider"})
    assert r.status_code == 501 and r.json()["fehler"].startswith("Adjusting by text")
