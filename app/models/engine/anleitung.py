"""Bauanleitung aus dem fertigen Modell: Teile-Buchstaben, Schritte mit „Das brauchst du“, Kopf mit Zeit und Kosten.

Was gute Anleitungen gemeinsam haben (Auswertung von gut 700 Anleitungen von OBI, toom, Hornbach, Festool,
Ana White u. a.): jedes Teil hat einen Buchstaben, der in Zuschnitt, Bild und Schritt gleich ist; jeder Schritt zeigt
nur die neuen Teile hervorgehoben und listet, was man dafür braucht; vorne stehen Schwierigkeit, Zeit und Kosten.
Die häufigsten Beschwerden betreffen Listen, die nicht zur Anleitung passen. Hier kommt alles aus demselben Modell.
"""
from __future__ import annotations

import string

from ...i18n import KATALOG, t
from .bauplan import MONTAGE, SCHRAUBEN_JE_VERBINDUNG, schraube
from .grundlagen import Bauteil, ext, mm

GURT_SCHRITT = "montage.gurte"
OBERFLAECHE = "montage.oberflaeche"


def _buchstabe(i: int) -> str:
    abc = string.ascii_uppercase
    return abc[i] if i < 26 else abc[i // 26 - 1] + abc[i % 26]


def _schluessel(m: Bauteil) -> tuple:
    """Gleiche Teile bekommen denselben Buchstaben: gleiches Holz, gleiche Maße (auf 1 mm)."""
    masse = tuple(sorted((mm(ext(m, a)) for a in (0, 1, 2)), reverse=True))
    return (m.typ, m.prof.get("label") or m.prof.get("t"), masse)


def schritte_und_buchstaben(ms: list[Bauteil]) -> tuple[list[tuple[str, list[Bauteil]]], dict[str, str]]:
    """Montageschritte (Textschlüssel, Teile) in Bau-Reihenfolge und Buchstabe je Teil-ID."""
    rest = list(ms)
    schritte: list[tuple[str, list[Bauteil]]] = []
    for rollen, key in MONTAGE:
        teile = [m for m in rest if m.rolle in rollen and m.typ != "gurt"]
        if key == "montage.5":  # Gurte vor der Lehne
            gurte = [m for m in rest if m.typ == "gurt"]
            if gurte:
                schritte.append((GURT_SCHRITT, gurte))
                rest = [m for m in rest if m.typ != "gurt"]
        if teile:
            schritte.append((key, teile))
            rest = [m for m in rest if m not in teile]
    gurte = [m for m in rest if m.typ == "gurt"]
    if gurte:
        schritte.append((GURT_SCHRITT, gurte))
    if [m for m in rest if m.typ != "gurt"]:
        schritte.append(("montage.rest", [m for m in rest if m.typ != "gurt"]))

    buchstaben: dict[str, str] = {}
    gruppen: dict[tuple, str] = {}
    for _, teile in schritte:
        for m in sorted(teile, key=lambda m: -max(ext(m, a) for a in (0, 1, 2))):
            if m.typ == "gurt":
                continue
            k = _schluessel(m)
            if k not in gruppen:
                gruppen[k] = _buchstabe(len(gruppen))
            buchstaben[m.id] = gruppen[k]
    return schritte, buchstaben


def _zaehlen(werte: list[str]) -> list[dict]:
    aus: dict[str, int] = {}
    for w in werte:
        aus[w] = aus.get(w, 0) + 1
    return [{"b": k, "n": n} for k, n in sorted(aus.items(), key=lambda kv: (len(kv[0]), kv[0]))]


def anleitung(ms: list[Bauteil], J: list[dict], plan: dict, dims: list[int], polster: float | None = None) -> dict:
    """Alles, was die Anleitung (Website, App, PDF) über die Bauliste hinaus braucht."""
    schritte, buchstaben = schritte_und_buchstaben(ms)

    # Teileliste: je Buchstabe ein Eintrag
    teileliste: dict[str, dict] = {}
    for m in ms:
        b = buchstaben.get(m.id)
        if not b:
            continue
        if b not in teileliste:
            masse = sorted((mm(ext(m, a)) for a in (0, 1, 2)), reverse=True)
            holz = m.prof.get("label") or t("plan.brett", t=m.prof.get("t"), w=masse[1])
            teileliste[b] = {"b": b, "n": 0, "name": m.name, "holz": holz, "laenge": masse[0],
                             "mass": "×".join(map(str, masse)), "ergaenzt": m.origin == "reparatur", "ids": []}
        teileliste[b]["n"] += 1
        teileliste[b]["ids"].append(m.id)

    # Schritte: neue Teile, Schrauben für die Verbindungen zu schon stehenden Teilen, Werkzeug, Tipp
    fertig: set[int] = set()
    aus = []
    for i, (key, teile) in enumerate(schritte):
        neu = {id(m) for m in teile}
        stehend = fertig | neu
        verbindungen = [j for j in J if (id(j["a"]) in neu or id(j["b"]) in neu)
                        and id(j["a"]) in stehend and id(j["b"]) in stehend]
        schrauben: dict[str, int] = {}
        for j in verbindungen:
            k = schraube(j)
            if k:
                schrauben[k] = schrauben.get(k, 0) + SCHRAUBEN_JE_VERBINDUNG
        werkzeug = ["akkuschrauber", "maßband", "bleistift"]
        if schrauben:
            werkzeug += ["bohrer"]
        if key in ("montage.1", "montage.2"):
            werkzeug += ["winkel", "zwingen"]
        if key == "montage.4":
            werkzeug += ["abstandsklotz"]
        if key == GURT_SCHRITT:
            werkzeug = ["tacker", "schere", "maßband"]
        if i == 0 and key == "montage.1" and any(m.rolle == "wandleiste" for m in teile):
            werkzeug += ["wasserwaage", "duebel"]
        text = next((s["t"] for s in plan["steps"] if s.get("key") == key), None) or t(key)
        aus.append({
            "nr": i + 1, "t": text, "ids": [m.id for m in teile], "n": len(teile),
            "teile": _zaehlen([buchstaben[m.id] for m in teile if m.id in buchstaben]),
            "gurte": sum(1 for m in teile if m.typ == "gurt"),
            "schrauben": [{"n": n, "text": t(f"schraube.{k}")} for k, n in schrauben.items()],
            "werkzeug": [t(f"werkzeug.{w}") for w in dict.fromkeys(werkzeug)],
            "tipp": t(f"tipp.{key.split('.')[1]}") if f"tipp.{key.split('.')[1]}" in KATALOG["de"] else "",
        })
        fertig |= neu
    aus.append({"nr": len(aus) + 1, "t": t(OBERFLAECHE), "ids": [], "n": 0, "teile": [], "gurte": 0, "schrauben": [],
                "werkzeug": [t("werkzeug.schleifpapier"), t("werkzeug.pinsel")], "tipp": t("tipp.oberflaeche")})

    # Kopf: Schwierigkeit, Zeit, Personen, Kosten
    holzteile = [m for m in ms if m.typ != "gurt"]
    n_schrauben = sum(h["n"] for h in plan["hardware"] if "×" in h["text"])
    stunden = 0.5 + len(holzteile) * 0.08 + n_schrauben * 0.02 + 1.0  # Aufbauen, Teile, Schrauben, Schleifen/Öl
    stunden = max(1.0, round(stunden * 2) / 2)
    stufe = 1 + (len(holzteile) > 15) + (len(holzteile) > 35) + (len(schritte) > 4) \
        + any(m.typ == "gurt" for m in ms)  # Gurte spannen braucht Übung
    gross = max(dims) > 1800 or sum(ext(m, 0) * ext(m, 1) * ext(m, 2) for m in holzteile) * 4.5e-7 > 25
    werkzeug_alle = [w for s in aus for w in s["werkzeug"]]
    return {
        "teileliste": sorted(teileliste.values(), key=lambda x: (len(x["b"]), x["b"])),
        "buchstaben": buchstaben,
        "schritte": aus,
        "werkzeug": list(dict.fromkeys(werkzeug_alle)),
        "kopf": {"stufe": min(5, stufe), "stunden": stunden, "personen": 2 if gross else 1,
                 "preis": plan.get("preis"), "polster": polster},
    }


__all__ = ["anleitung", "schritte_und_buchstaben"]
