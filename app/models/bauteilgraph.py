"""Bauteilgraph: die Beschreibung eines Möbels, wie Claude sie aus einem Entwurfsbild liest.

Die Engine rechnet daraus Maße, Verbindungen und Statik. Antworten der KI sind nie ganz sauber, deshalb wird
jeder Graph vor der Verwendung geprüft und auf gültige Werte gebracht.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from .engine.grundlagen import mm

TYPEN = ["latte", "kantholz", "brett", "platte"]
ROLLEN = ["riegel", "wandleiste", "bein", "pfosten", "kufe", "rahmen", "zarge", "auflage", "leiste", "lattenrost",
          "sitzflaeche", "liegeflaeche", "regalboden", "lehne", "verkleidung"]
MAX_TEILE = 40

GRAPH_SCHEMA = """Bauteilgraph (JSON). Koordinaten relativ 0..1 im Hüllquader des Möbels: x = Breite links→rechts, y = Tiefe (0 = vorne, 1 = hinten/Wand), z = Höhe (0 = Boden).
{
 "name": "kurzer Name",
 "kategorie": "bett|daybed|sofa|bank|regal|tisch|sonstiges",
 "masse": {"breite": mm, "tiefe": mm, "hoehe": mm},            // grobe Schätzung aus dem Bild
 "funktion": {"matratze": [900,2000], "luft": 10} oder {"sitzhoehe": 450, "polster": 80} oder {},
 "anker": {"liegeflaeche": [x0,x1,y0,y1]} bzw. {"sitz_oben": z}, // relative Lage der Funktionsfläche (Oberkante Sitzbretter ohne Polster). Steht die Matratze über den Rahmen über, liegen x0/y0 unter 0 und x1/y1 über 1.
 "teile": [ {"id": "kurz", "name": "Deutsch", "typ": "latte|kantholz|brett|platte",
            "rolle": "wandleiste|bein|pfosten|kufe|rahmen|zarge|auflage|leiste|lattenrost|sitzflaeche|regalboden|lehne|verkleidung",
            "box": [x0,x1,y0,y1,z0,z1], "anzahl": n, "achse": "x|y|z", "querschnitt": [mm,mm]} ]
}
Regeln: "box" ist der Bereich, den das Teil bzw. die Teilegruppe einnimmt. Bei anzahl > 1 werden die Teile gleichmäßig entlang "achse" in der Box verteilt.
"querschnitt" = geschätzter Querschnitt eines Stücks. Sortiment: Latte 24×44, Rahmenholz 34×54, 44×44, 44×74, 44×94, Leimholz 18 oder 28 mm (Bretter beliebig breit bis 600, Länge bis 2000).
"wandleiste" = an die Wand geschraubte Leiste, trägt mit. "leiste" = verbindende Leiste ohne Last (z. B. Querleisten unter einem Deckel). "auflage" trägt etwas, das darauf liegt.
Beschreibe nur, was man im Bild sieht. Exakte Maße, Verbindungen, Statik und Reparaturen rechnet danach Code."""


class GraphFehler(ValueError):
    """Der Bauteilgraph ist unbrauchbar."""


def json_aus_text(text: str) -> Any:
    """JSON aus einer KI-Antwort holen, auch wenn es in einem Codeblock oder in Fließtext steckt."""
    try:
        return json.loads(text)
    except ValueError:
        pass
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        try:
            return json.loads(fence.group(1))
        except ValueError:
            pass
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        try:
            return json.loads(text[a:b + 1])
        except ValueError as e:
            raise GraphFehler(f"Antwort ist kein gültiges JSON: {e}") from e
    raise GraphFehler("Keine JSON-Antwort gefunden.")


def _zahl(v: Any) -> float | None:
    if isinstance(v, bool):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _int_wenn_ganz(x: float) -> int | float:
    return int(x) if float(x).is_integer() else x


def _positiv(v: Any, ersatz: float) -> int | float:
    x = _zahl(v)
    return _int_wenn_ganz(x) if x is not None and x > 0 else ersatz


def bereinigen(j: Any) -> dict:
    """Graph prüfen und auf gültige Werte bringen. Wirft ``GraphFehler``, wenn er nicht zu retten ist."""
    if not isinstance(j, dict) or not isinstance(j.get("teile"), list) or not j["teile"]:
        raise GraphFehler("Der Bauteilgraph enthält keine Teile.")
    m = j.get("masse") if isinstance(j.get("masse"), dict) else {}
    masse = {"breite": _positiv(m.get("breite"), 1500), "tiefe": _positiv(m.get("tiefe"), 600), "hoehe": _positiv(m.get("hoehe"), 800)}

    teile = []
    for i, t in enumerate(j["teile"][:MAX_TEILE]):
        if not isinstance(t, dict):
            raise GraphFehler(f"Teil {i + 1}: kein Objekt.")
        roh = t.get("box") if isinstance(t.get("box"), list) else []
        b = [_zahl(v) for v in roh]
        if len(b) != 6 or any(v is None for v in b):
            raise GraphFehler(f"Teil {i + 1}: Lage (box) fehlt.")
        box: list[float] = []
        for k in (0, 2, 4):
            lo = max(0.0, min(1.0, min(b[k], b[k + 1])))
            hi = max(0.0, min(1.0, max(b[k], b[k + 1])))
            box += [_int_wenn_ganz(lo), _int_wenn_ganz(max(hi, lo + 0.005))]
        anzahl = _zahl(t.get("anzahl")) or 1
        qs = t.get("querschnitt")
        querschnitt = [_zahl(v) for v in qs] if isinstance(qs, list) and len(qs) == 2 else None
        teil = {
            "id": str(t.get("id") or f"t{i + 1}")[:30],
            "name": str(t.get("name") or t.get("id") or f"Teil {i + 1}")[:40],
            "typ": t.get("typ") if t.get("typ") in TYPEN else "latte",
            "rolle": t.get("rolle") if t.get("rolle") in ROLLEN else "rahmen",
            "box": box,
            "anzahl": max(1, min(40, mm(anzahl))),
            "achse": t.get("achse") if t.get("achse") in ("x", "y", "z") else "x",
        }
        if querschnitt and all(v is not None for v in querschnitt):
            teil["querschnitt"] = [_int_wenn_ganz(v) for v in querschnitt]
        teile.append(teil)
    ids: set[str] = set()
    for t in teile:
        while t["id"] in ids:
            t["id"] += "x"
        ids.add(t["id"])

    f = j.get("funktion") if isinstance(j.get("funktion"), dict) else {}
    a = j.get("anker") if isinstance(j.get("anker"), dict) else {}
    funktion: dict = {}
    anker: dict = {}
    mat, lf = f.get("matratze"), a.get("liegeflaeche")
    if isinstance(mat, list) and len(mat) == 2 and isinstance(lf, list) and len(lf) == 4 \
            and all(_zahl(v) is not None for v in mat + lf):
        funktion = {"matratze": [_int_wenn_ganz(_zahl(v)) for v in mat], "luft": _positiv(f.get("luft"), 10)}
        anker = {"liegeflaeche": [_int_wenn_ganz(_zahl(v)) for v in lf]}
    elif _positiv(f.get("sitzhoehe"), 0) and (_zahl(a.get("sitz_oben")) or 0) > 0:
        funktion = {"sitzhoehe": _int_wenn_ganz(_zahl(f["sitzhoehe"])), "polster": _positiv(f.get("polster"), 0)}
        anker = {"sitz_oben": _int_wenn_ganz(_zahl(a["sitz_oben"]))}
    return {"name": str(j.get("name") or "Möbel")[:40], "kategorie": str(j.get("kategorie") or "sonstiges"),
            "masse": masse, "funktion": funktion, "anker": anker, "teile": teile}
