"""Bauteil-Engine: Bauteilgraph (aus der Bildlesung) → baubares, stabiles Modell → Bauplan.

Ablauf: skalieren → einrasten → setzen → prüfen und reparieren → Endkontrolle → Nachführen → Bauplan.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..sortiment import SORTIMENTE, Sortiment
from ...i18n import t
from .aufbau import aufbauen, skalieren
from .bauplan import bauplan, polster
from .grundlagen import Bauteil, einmalig, gesetzt, mm, zahl
from .pruefung import endkontrolle
from .reparatur import pruefen_und_reparieren
from .setzen import kontakte, setzen


@dataclass
class Ergebnis:
    steps: list[dict]
    members: list[Bauteil]
    dims: list[int]
    joints: list[dict]
    repairs: list[str]
    fc: dict
    plan: dict = field(default_factory=dict)
    soft: list[dict] = field(default_factory=list)
    graph: dict = field(default_factory=dict)

    @property
    def checks(self) -> list[dict]:
        return self.fc["checks"]

    @property
    def offene_punkte(self) -> int:
        return sum(1 for c in self.checks if c["ok"] is False)

    def als_dict(self) -> dict:
        return {
            "dims": self.dims,
            "steps": [{k: v for k, v in s.items() if k != "reparaturen"} for s in self.steps],
            "repairs": self.repairs,
            "members": [m.als_dict() for m in self.members],
            "joints": [[j["a"].id, j["b"].id, j["ax"]] for j in self.joints],
            "plan": self.plan,
            "soft": self.soft,
            "fc": {k: self.fc.get(k) for k in ("checks", "dims", "bb", "clear", "mat", "seat")},
        }


def _durchlauf(S: Sortiment, g: dict, bereich, dims: list[int], l1: list[str]) -> Ergebnis:
    steps = [{"key": "skalieren", "title": t("schritt.skalieren"), "log": l1}]
    l2: list[str] = []
    members, groups = aufbauen(S, g, dims, l2)
    steps.append({"key": "einrasten", "title": t("schritt.einrasten"), "log": l2})

    l3: list[str] = []
    st = setzen(members, l3)
    l3.insert(0, t("log.verschoben", n=len(st.get("ids", ())), gesamt=len(members), max=mm(st["max"])))
    steps.append({"key": "kontakte", "title": t("schritt.kontakte"), "log": l3})

    l4: list[str] = []
    repairs: list[str] = []
    pruefen_und_reparieren(S, members, groups, g, l4, repairs)
    l4u = einmalig(l4)
    steps.append({"key": "reparieren", "title": t("schritt.reparieren"), "reparaturen": len(repairs),
                  "log": [*repairs, *l4u] if repairs else [t("log.keine_reparatur"), *l4u]})

    # Ursprung in die vordere linke Ecke am Boden legen
    o = [min(m.min[a] for m in members) for a in (0, 1, 2)]
    for m in members:
        for a in (0, 1, 2):
            m.min[a] -= o[a]
            m.max[a] -= o[a]
    J = kontakte(members)
    fc = endkontrolle(members, g, bereich, J)
    steps.append({"key": "pruefen", "title": t("schritt.pruefen"), "checks": fc["checks"]})
    return Ergebnis(steps=steps, members=members, dims=fc["dims"], joints=J, repairs=repairs, fc=fc)


def berechnen(graph: dict, bereich: list[float] | None = None, sortiment: str = "DE") -> Ergebnis:
    """Bauteilgraph in ein baubares Modell mit Bauplan umrechnen.

    ``bereich``: verfügbarer Platz Breite × Tiefe × Höhe in mm. ``sortiment``: "DE" (Baumarkt) oder "US" (Bauholz).
    """
    S = SORTIMENTE["US" if sortiment == "US" else "DE"]
    g = copy.deepcopy(graph)
    if sortiment == "US":
        for teil in g["teile"]:
            if teil.get("typ") == "brett" and not teil.get("platte"):
                teil["typ"] = "latte"
    l1: list[str] = []
    dims = skalieren(g, l1)
    out = _durchlauf(S, g, bereich, dims, l1)

    # Nachführen: liegt die Funktionsfläche nach dem Bauen daneben, Gesamtmaß korrigieren und neu rechnen
    for durchgang in range(2):
        f = g.get("funktion") or {}
        d = list(dims)
        notes = []
        if gesetzt(f.get("matratze")) and out.fc.get("clear") is not None:
            luft = 10 if f.get("luft") is None else f["luft"]
            for ax, v in enumerate(out.fc["clear"]):
                if v is None:
                    continue
                want = out.fc["mat"][ax] + luft
                if abs(v - want) > 15 and abs(v - want) < 0.25 * want:
                    d[ax] -= v - want
                    notes.append(t("nach.liegeflaeche", achse=t("wort.tiefe") if ax else t("wort.breite"), v=v, want=zahl(want),
                                   diff=mm(v - want), richtung=t("wort.verringert") if v > want else t("wort.vergroessert")))
        seat = out.fc.get("seat")
        if gesetzt(f.get("sitzhoehe")) and seat is not None and abs(seat - f["sitzhoehe"]) > 15:
            # nur kleine Korrekturen wie beim Bett (unter 25 %); große Abweichungen sind ein Lesefehler, kein Rundungsfehler
            if abs(seat - f["sitzhoehe"]) < 0.25 * f["sitzhoehe"]:
                d[2] = d[2] * (f["sitzhoehe"] / seat)
                notes.append(t("nach.sitz", ist=seat, soll=zahl(f["sitzhoehe"])))
        if bereich is not None and not gesetzt(f.get("matratze")):  # beim Bett bestimmt die Matratze Breite und Tiefe
            for ax, wort in ((0, t("wort.breite")), (1, t("wort.tiefe"))):
                over = out.dims[ax] - bereich[ax]
                if 0 < over < 0.25 * bereich[ax]:
                    d[ax] -= over
                    notes.append(t("nach.bereich", achse=wort, ist=out.dims[ax], soll=zahl(bereich[ax]), diff=mm(over)))
        if not notes:
            break
        neue_dims = [mm(v) for v in d]
        neu = _durchlauf(S, g, bereich, neue_dims, [*l1, t("nach.durchlauf", n=durchgang + 2, notes="; ".join(notes))])
        if neu.offene_punkte > out.offene_punkte:
            break  # die Korrektur hätte mehr Probleme gemacht als gelöst: beim vorigen Stand bleiben
        dims, out = neue_dims, neu

    out.plan = bauplan(S, out.members, out.joints)
    out.soft = polster(g, out.members, out.dims)
    out.graph = graph
    return out


__all__ = ["berechnen", "Ergebnis", "Bauteil"]
