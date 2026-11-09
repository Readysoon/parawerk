"""Bauteil-Engine: Bauteilgraph (aus der Bildlesung) → baubares, stabiles Modell → Bauplan.

Ablauf: skalieren → einrasten → setzen → prüfen und reparieren → Endkontrolle → Nachführen → Bauplan.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..sortiment import SORTIMENTE, Sortiment
from ...i18n import holz, t
from . import gurte
from .aufbau import RAND_MM, _strecken, aufbauen, skalieren
from .bauplan import bauplan, polster
from .grundlagen import Bauteil, einmalig, gesetzt, mm, zahl
from .pruefung import endkontrolle
from . import sicherheit
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


# Handelsübliche Matratzen (mm): Breiten und Längen
MATRATZE_BREITEN = [800, 900, 1000, 1200, 1400, 1600, 1800, 2000]
MATRATZE_LAENGEN = [1900, 2000, 2100, 2200]


def _naechste(werte: list[int], ziel: float) -> int:
    return min(werte, key=lambda v: abs(v - ziel))


def _ziel_anwenden(g: dict, ziel: list[float], referenz: list[int], log: list[str], rand: float = RAND_MM) -> list[int]:
    """Wunschmaße (Strecken/Stauchen) in den Graph übernehmen und die zu bauenden Gesamtmaße liefern.

    Beim Bett springt die Liegefläche auf eine handelsübliche Matratze; beim Sitzmöbel wächst die Sitzhöhe mit.
    """
    f, a = g.get("funktion") or {}, g.get("anker") or {}
    dims = [mm(v) for v in ziel]
    if gesetzt(f.get("matratze")) and gesetzt(a.get("liegeflaeche")):
        x0, x1, y0, y1 = a["liegeflaeche"]
        luft = 10 if f.get("luft") is None else f["luft"]
        lx, ly = (x1 - x0) * dims[0] - luft, (y1 - y0) * dims[1] - luft  # Liegefläche bei den Wunschmaßen
        lang_x = (x1 - x0) * referenz[0] >= (y1 - y0) * referenz[1]  # Liegerichtung bleibt wie im Design
        lang, kurz = (lx, ly) if lang_x else (ly, lx)
        mat = [_naechste(MATRATZE_BREITEN, kurz), _naechste(MATRATZE_LAENGEN, lang)]
        f["matratze"] = mat
        log.append(t("log.ziel_matratze", mat=" × ".join(map(str, mat))))
        dims[0] = mm(((mat[1] if lang_x else mat[0]) + luft) / (x1 - x0))
        dims[1] = mm(((mat[0] if lang_x else mat[1]) + luft) / (y1 - y0))
    if gesetzt(f.get("sitzhoehe")) and a.get("sitz_oben") is not None:
        # Sitzhöhe so, wie die Sitzfläche beim Strecken tatsächlich wandert (nah am Boden bleibt sie, wo sie ist)
        f["sitzhoehe"] = mm(_strecken(a["sitz_oben"], referenz[2], dims[2], rand) + (f.get("polster") or 0))
    log.append(t("log.ziel", rw=referenz[0], rd=referenz[1], rh=referenz[2], w=dims[0], d=dims[1], h=dims[2]))
    return dims


def _durchlauf(S: Sortiment, g: dict, bereich, dims: list[int], l1: list[str],
               referenz: list[int] | None = None, rand: float = RAND_MM) -> Ergebnis:
    steps = [{"key": "skalieren", "title": t("schritt.skalieren"), "log": l1}]
    l2: list[str] = []
    members, groups = aufbauen(S, g, dims, l2, referenz, rand)
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


def berechnen(graph: dict, bereich: list[float] | None = None, sortiment: str = "DE", schnell: bool = False) -> Ergebnis:
    """Bauteilgraph in ein baubares Modell mit Bauplan umrechnen.

    ``bereich``: verfügbarer Platz Breite × Tiefe × Höhe in mm. ``sortiment``: "DE" (Baumarkt) oder "US" (Bauholz).
    Hat der Graph ``ziel`` (Wunschmaße), wird das Design gestreckt bzw. gestaucht, bis das gebaute Außenmaß passt.
    ``schnell``: für die Vorschau beim Ziehen eines Reglers (weniger Nachstellen, keine zweite Streckart).
    """
    S = SORTIMENTE["US" if sortiment == "US" else "DE"]
    g = gurte.umstellen(graph) if graph.get("sitz") == "gurte" else copy.deepcopy(graph)
    if sortiment == "US":
        for teil in g["teile"]:
            if teil.get("typ") == "brett" and not teil.get("platte"):
                teil["typ"] = "latte"

    def rechne(gg: dict) -> Ergebnis:
        ziel = gg.get("ziel")
        if not gesetzt(ziel):
            return _rechnen(S, gg, bereich, None)
        # Das gebaute Außenmaß ist etwas größer als das Rastermaß (Holzstärken stehen über): nachstellen, bis es passt
        # Zwei Arten zu strecken: Kanten nah am Rand behalten ihren Abstand (meist besser), oder alles anteilig.
        # Die zweite wird nur probiert, wenn die erste offene Punkte hat; es gilt die mit weniger offenen Punkten.
        aus = _strecken_bis_passt(S, gg, bereich, ziel, RAND_MM, 2 if schnell else 3)
        if _probleme(aus) and not schnell:
            anteilig = _strecken_bis_passt(S, gg, bereich, ziel, 0)
            if _probleme(anteilig) < _probleme(aus):
                aus = anteilig
        return aus

    out = rechne(g)
    if not schnell:
        # Die Reparatur entscheidet je Teil, ob stärkeres Holz oder ein Steg weniger Holz braucht. Im Ganzen kann es
        # anders ausgehen (eine Stütze zieht Fußriegel nach sich): darum auch „immer erst stärkeres Holz“ rechnen und
        # das Ergebnis mit weniger offenen Punkten, sonst mit weniger Holz nehmen.
        g2 = {**g, "_reparatur": "staerker"}
        anders = rechne(g2)
        if (anders.offene_punkte, _holz(anders)) < (out.offene_punkte, _holz(out)):
            out, g = anders, g2
        out = _sparen(S, g, out, rechne)
    out.graph = graph
    return out


# Teile, die man am fertigen Möbel kaum sieht: dürfen schlanker werden als im Entwurf, wenn die Statik es erlaubt
VERSTECKT = {"zarge", "mittelsteg", "querriegel", "auflage", "wandleiste"}
SPAR_RESERVE = 0.85  # neue Ausnutzung höchstens 85 %, damit die Abschätzung vor dem Nachrechnen Luft hat


def _holz(e: Ergebnis) -> float:
    return sum((m.max[0] - m.min[0]) * (m.max[1] - m.min[1]) * (m.max[2] - m.min[2]) for m in e.members)


def _ergaenzt(e: Ergebnis) -> int:
    return sum(1 for m in e.members if m.origin == "reparatur")


def _sparen(S: Sortiment, g: dict, out: Ergebnis, rechne) -> Ergebnis:
    """Minimaler Holzverbrauch: versteckte Kanthölzer auf den kleinsten Querschnitt, der die Normlasten noch hält.

    Abschätzung über Widerstands- und Trägheitsmoment, danach wird alles neu gerechnet und nur übernommen, wenn
    dabei nichts schlechter wird (offene Punkte, Statik). Sichtbare Teile bleiben, wie sie im Entwurf sind.
    """
    st = out.fc.get("statik")
    if st is None:
        return out
    nutzung: dict[str, float] = {}
    for n in st.nachweise:
        nutzung[n.teil.part] = max(nutzung.get(n.teil.part, 0.0), n.ausnutzung)
    vorschlaege: dict[str, tuple[dict, dict, float]] = {}
    for p in g["teile"]:
        if p.get("rolle") not in VERSTECKT or p.get("typ") != "kantholz":
            continue
        ms = [m for m in out.members if m.part == p["id"] and m.origin == "entwurf"]
        if not ms or ms[0].long == 2 or "label" not in ms[0].prof:
            continue
        m = ms[0]
        quer = next(a for a in (0, 1) if a != m.long)
        b, h = m.max[quer] - m.min[quer], m.max[2] - m.min[2]
        u = nutzung.get(p["id"], 0.0)
        alt = next((k for k in S["kantholz"] if k["label"] == m.prof["label"]), None)
        if alt is None:
            continue
        for k in sorted(S["kantholz"], key=lambda k: k["a"] * k["b"]):
            if k["a"] * k["b"] >= alt["a"] * alt["b"]:
                break
            kb, kh = min(k["a"], k["b"]), max(k["a"], k["b"])
            faktor = max((b * h * h) / (kb * kh * kh), (b * h ** 3) / (kb * kh ** 3))
            if u * faktor <= SPAR_RESERVE:
                vorschlaege[p["id"]] = (alt, k, u * faktor)
                break
    if not vorschlaege:
        return out

    def versuchen(ids: list[str]) -> Ergebnis | None:
        gg = copy.deepcopy(g)
        for teil in gg["teile"]:
            if teil["id"] in ids:
                teil["_profil"] = vorschlaege[teil["id"]][1]["label"]
        neu = rechne(gg)
        schlechtester = neu.fc["statik"].schlechtester
        if neu.offene_punkte > out.offene_punkte or (schlechtester is not None and schlechtester.ausnutzung > 1
                                                      and (st.schlechtester is None or st.schlechtester.ausnutzung <= 1)):
            return None
        # nur übernehmen, wenn wirklich Holz gespart wird und dafür keine Stützen oder Stege dazukommen
        if _ergaenzt(neu) > _ergaenzt(out) or _holz(neu) >= _holz(out):
            return None
        return neu

    angenommen = list(vorschlaege)
    neu = versuchen(angenommen)
    if neu is None:  # gemeinsam ging es nicht: einzeln probieren
        angenommen = [i for i in vorschlaege if versuchen([i]) is not None]
        neu = versuchen(angenommen) if angenommen else None
    if neu is None:
        return out
    namen = {p["id"]: p.get("name") or p["id"] for p in g["teile"]}
    zeilen = [t("rep.sparsam" if vorschlaege[i][2] >= 0.05 else "rep.sparsam_leer", name=namen[i],
                alt=holz(vorschlaege[i][0]["label"]), neu=holz(vorschlaege[i][1]["label"]), p=mm(vorschlaege[i][2] * 100))
              for i in angenommen]
    neu.repairs.extend(zeilen)
    for schritt in neu.steps:
        if schritt["key"] == "reparieren":
            schritt["log"] = [*zeilen, *schritt["log"]]
    return neu


def _probleme(e: Ergebnis) -> int:
    """Offene Punkte, die das Strecken verursacht haben kann (eine Sitzhöhe außerhalb der Norm ist gewollt)."""
    return e.offene_punkte - (1 if e.fc.get("seat_ok") is False else 0)


def _strecken_bis_passt(S: Sortiment, g: dict, bereich, ziel: list[float], rand: float, versuche: int = 3) -> Ergebnis:
    """Das gebaute Außenmaß ist etwas größer als das Rastermaß (Holzstärken stehen über): nachstellen, bis es passt."""
    bett = gesetzt((g.get("funktion") or {}).get("matratze"))
    soll = [float(v) for v in ziel]
    for _ in range(versuche):
        out = _rechnen(S, copy.deepcopy(g), bereich, soll, rand)
        diff = [ziel[a] - out.dims[a] for a in (0, 1, 2)]
        if bett:  # Breite und Tiefe springen auf Matratzengrößen
            diff[0] = diff[1] = 0
        if all(abs(d) <= 5 for d in diff):
            break
        soll = [max(100.0, soll[a] + diff[a]) for a in (0, 1, 2)]
    return out


def _rechnen(S: Sortiment, g: dict, bereich, soll: list[float] | None, rand: float = RAND_MM) -> Ergebnis:
    l1: list[str] = []
    dims = skalieren(g, l1)
    referenz = None
    if soll is not None:  # Strecken/Stauchen: das Design gilt für die gelesenen Maße, gebaut wird in Wunschgröße
        referenz = dims
        dims = _ziel_anwenden(g, soll, referenz, l1, rand)
    out = _durchlauf(S, g, bereich, dims, l1, referenz, rand)

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
        # beim Bett bestimmt die Matratze Breite und Tiefe; Wunschmaße gehen vor dem Bereich
        if bereich is not None and not gesetzt(f.get("matratze")) and referenz is None:
            for ax, wort in ((0, t("wort.breite")), (1, t("wort.tiefe"))):
                over = out.dims[ax] - bereich[ax]
                if 0 < over < 0.25 * bereich[ax]:
                    d[ax] -= over
                    notes.append(t("nach.bereich", achse=wort, ist=out.dims[ax], soll=zahl(bereich[ax]), diff=mm(over)))
        if not notes:
            break
        neue_dims = [mm(v) for v in d]
        neu = _durchlauf(S, g, bereich, neue_dims, [*l1, t("nach.durchlauf", n=durchgang + 2, notes="; ".join(notes))],
                         referenz, rand)
        if neu.offene_punkte > out.offene_punkte:
            break  # die Korrektur hätte mehr Probleme gemacht als gelöst: beim vorigen Stand bleiben
        dims, out = neue_dims, neu

    schaum = (g.get("funktion") or {}).get("polster") if any(m.typ == "gurt" for m in out.members) else None
    out.plan = bauplan(S, out.members, out.joints, schaum)
    out.soft = polster(g, out.members, out.dims)
    if sicherheit.braucht_kippsicherung(out.members, g):
        out.plan["hardware"].append({"n": 2, "text": t("kippsicherung.hw"), "preis": sicherheit.KIPPSICHERUNG_PREIS})
        if out.plan.get("preis") is not None:
            out.plan["preis"] = round(out.plan["preis"] + sicherheit.KIPPSICHERUNG_PREIS, 2)
        out.plan["steps"].append({"t": t("montage.kippsicherung"), "n": 2, "key": "montage.kippsicherung"})
        out.fc["checks"].append({"ok": True, "t": t("chk.kippsicherung")})
    return out


__all__ = ["berechnen", "Ergebnis", "Bauteil"]
