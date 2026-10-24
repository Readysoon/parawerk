"""Aufbereitung des Engine-Ergebnisses für die Anzeige (was die Templates brauchen, fertig gerechnet)."""
from __future__ import annotations

import json

from ..i18n import dez, sprache, t
from ..models.engine import Ergebnis
from ..models.engine.grundlagen import fest, zahl

STATUS = {True: ("ok", "bp.st_ok"), False: ("no", "bp.st_no"), None: ("info", "bp.st_info")}


def eur(v: float) -> str:
    return f"{dez(fest(v, 2))} €" if sprache() == "de" else f"€{fest(v, 2)}"


def meter(v: float) -> str:
    return dez(fest(v / 1000, 2))


def _prozent(teil: float, ganzes: float) -> str:
    return f"{teil / ganzes * 100:.3f}%"


def _stangen(bins: list[dict], ergaenzt: set[str]) -> list[dict]:
    """Gleich zugeschnittene Stangen zusammenfassen."""
    gruppen: dict[str, dict] = {}
    for b in bins:
        k = f"{b['L']}|" + ",".join(f"{i['len']}{'r' if i['id'] in ergaenzt else ''}" for i in b["items"])
        if k not in gruppen:
            gruppen[k] = {
                "anzahl": 0, "laenge": b["L"], "zu_lang": bool(b.get("too_long")),
                "rest": 0 if b.get("too_long") else b["L"] - b["used"],
                "stuecke": [{"len": i["len"], "name": i["name"], "ergaenzt": i["id"] in ergaenzt,
                             "breite": _prozent(i["len"], b["L"])} for i in b["items"]],
            }
        gruppen[k]["anzahl"] += 1
    return list(gruppen.values())


def _platten(cg: dict) -> list[list[dict]]:
    return [[{"l": it["l"], "w": it["w"], "name": it["name"], "links": _prozent(it["x"], cg["L"]), "oben": _prozent(it["y"], cg["W"]),
              "breite": _prozent(it["l"], cg["L"]), "hoehe": _prozent(it["w"], cg["W"])}
             for st in s["strips"] for it in st["items"]] for s in cg["sheets"]]


def bauplan_ansicht(e: Ergebnis, graph: dict, bereich: list[float]) -> dict:
    ergaenzt = {m.id for m in e.members if m.origin == "reparatur"}
    zuschnitt = []
    for cg in e.plan["cut_groups"]:
        if cg["kind"] == "stab":
            zuschnitt.append({"art": "stab", "label": cg["label"], "stangen": _stangen(cg["bins"], ergaenzt)})
        else:
            zuschnitt.append({"art": "platte", "label": cg["label"], "seitenverhaeltnis": f"{cg['L']}/{cg['W']}",
                              "platten": _platten(cg)})
    return {
        "name": graph["name"],
        "offene_punkte": e.offene_punkte,
        "pruefungen": [{"klasse": STATUS[c["ok"]][0], "status": t(STATUS[c["ok"]][1]), "text": c["t"]} for c in e.checks],
        "rechenweg": [{"titel": s["title"], "zeilen": [{"text": l, "reparatur": i < s.get("reparaturen", 0)}
                                                       for i, l in enumerate(s["log"])]}
                      for s in e.steps if "log" in s],
        "anzahl_gruppen": len(graph["teile"]),
        "graph_json": json.dumps(graph, ensure_ascii=False, indent=1),
        "einkauf": e.plan["lines"],
        "beschlaege": e.plan["hardware"],
        "schnitte": e.plan["cuts"],
        "schnittkosten": e.plan["cost"],
        "montage": e.plan["steps"],
        "zuschnitt": zuschnitt,
        "aussenmass": " × ".join(map(str, e.dims)),
        "bereich": " × ".join(zahl(v) for v in bereich),
        "anzahl_teile": len(e.members),
        "anzahl_ergaenzt": len(ergaenzt),
    }


def modell_3d(e: Ergebnis) -> dict:
    """Nur was die 3D-Ansicht im Browser braucht."""
    return {
        "dims": e.dims,
        "teile": [{"min": m.min, "max": m.max, "ergaenzt": m.origin == "reparatur", "name": m.name} for m in e.members],
        "polster": e.soft,
    }
