"""Aufbereitung des Engine-Ergebnisses für die Anzeige (was die Templates brauchen, fertig gerechnet)."""
from __future__ import annotations

import json

from ..i18n import dez, sprache, t
from ..models.engine import Ergebnis
from ..models.engine.anleitung import anleitung, schritte_und_buchstaben
from ..models.engine.grundlagen import fest, zahl

STATUS = {True: ("ok", "bp.st_ok"), False: ("no", "bp.st_no"), None: ("info", "bp.st_info")}


def eur(v: float) -> str:
    return f"{dez(fest(v, 2))} €" if sprache() == "de" else f"€{fest(v, 2)}"


def meter(v: float) -> str:
    return dez(fest(v / 1000, 2))


def _prozent(teil: float, ganzes: float) -> str:
    return f"{teil / ganzes * 100:.3f}%"


def _stangen(bins: list[dict], ergaenzt: set[str], buchstaben: dict[str, str] | None = None) -> list[dict]:
    """Gleich zugeschnittene Stangen zusammenfassen."""
    buchstaben = buchstaben or {}
    gruppen: dict[str, dict] = {}
    for b in bins:
        k = f"{b['L']}|" + ",".join(f"{i['len']}{'r' if i['id'] in ergaenzt else ''}{buchstaben.get(i['id'], '')}"
                                     for i in b["items"])
        if k not in gruppen:
            gruppen[k] = {
                "anzahl": 0, "laenge": b["L"], "zu_lang": bool(b.get("too_long")),
                "rest": 0 if b.get("too_long") else b["L"] - b["used"],
                "stuecke": [{"len": i["len"], "name": i["name"], "ergaenzt": i["id"] in ergaenzt,
                             "b": buchstaben.get(i["id"], ""),
                             "breite": _prozent(i["len"], b["L"])} for i in b["items"]],
            }
        gruppen[k]["anzahl"] += 1
    return list(gruppen.values())


def _platten(cg: dict, buchstaben: dict[str, str] | None = None) -> list[list[dict]]:
    buchstaben = buchstaben or {}
    return [[{"l": it["l"], "w": it["w"], "name": it["name"], "b": buchstaben.get(it["id"], ""), "links": _prozent(it["x"], cg["L"]), "oben": _prozent(it["y"], cg["W"]),
              "breite": _prozent(it["l"], cg["L"]), "hoehe": _prozent(it["w"], cg["W"])}
             for st in s["strips"] for it in st["items"]] for s in cg["sheets"]]


def bauplan_ansicht(e: Ergebnis, graph: dict, bereich: list[float]) -> dict:
    ergaenzt = {m.id for m in e.members if m.origin == "reparatur"}
    polster = (graph.get("funktion") or {}).get("polster")
    an = anleitung(e.members, e.joints, e.plan, e.dims, polster)
    bs = an["buchstaben"]
    zuschnitt = []
    for cg in e.plan["cut_groups"]:
        if cg["kind"] == "stab":
            zuschnitt.append({"art": "stab", "label": cg["label"], "stangen": _stangen(cg["bins"], ergaenzt, bs)})
        else:
            zuschnitt.append({"art": "platte", "label": cg["label"], "seitenverhaeltnis": f"{cg['L']}/{cg['W']}",
                              "platten": _platten(cg, bs)})
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
        "montage": [{"t": s["t"], "n": s["n"], "teile": ", ".join(f"{x['n']}× {x['b']}" for x in s["teile"])}
                    for s in an["schritte"]],
        "schritte": an["schritte"],
        "teileliste": an["teileliste"],
        "werkzeug": an["werkzeug"],
        "kopf": {**an["kopf"], "preis_text": eur(an["kopf"]["preis"]) if an["kopf"]["preis"] else None},
        "zuschnitt": zuschnitt,
        "aussenmass": " × ".join(map(str, e.dims)),
        "bereich": " × ".join(zahl(v) for v in bereich),
        "anzahl_teile": len(e.members),
        "anzahl_ergaenzt": len(ergaenzt),
    }


def modell_3d(e: Ergebnis) -> dict:
    """Nur was die 3D-Ansicht im Browser braucht."""
    _, bs = schritte_und_buchstaben(e.members)
    return {
        "dims": e.dims,
        "teile": [{"min": m.min, "max": m.max, "ergaenzt": m.origin == "reparatur", "name": m.name, "id": m.id,
                   **({"b": bs[m.id]} if m.id in bs else {}),
                   **({"gurt": True} if m.typ == "gurt" else {})} for m in e.members],
        "polster": e.soft,
    }
