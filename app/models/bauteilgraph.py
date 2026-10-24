"""Bauteilgraph: die Beschreibung eines Möbels, wie Claude sie aus einem Entwurfsbild liest.

Die Engine rechnet daraus Maße, Verbindungen und Statik. Antworten der KI sind nie ganz sauber, deshalb wird
jeder Graph vor der Verwendung geprüft und auf gültige Werte gebracht.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

from ..i18n import t as tr
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


def _entschaerfen(text: str) -> str:
    """Kommentare (// und /* */) außerhalb von Strings und Kommas vor ] oder } entfernen."""
    aus: list[str] = []
    i, n, im_string = 0, len(text), False
    while i < n:
        c = text[i]
        if im_string:
            aus.append(c)
            if c == "\\" and i + 1 < n:
                aus.append(text[i + 1])
                i += 1
            elif c == '"':
                im_string = False
        elif c == '"':
            im_string = True
            aus.append(c)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            ende = text.find("*/", i + 2)
            i = n if ende < 0 else ende + 2
            continue
        else:
            aus.append(c)
        i += 1
    return re.sub(r",(\s*[\]}])", r"\1", "".join(aus))


def json_aus_text(text: str) -> Any:
    """JSON aus einer KI-Antwort holen, auch aus Codeblöcken, Fließtext oder mit Kommentaren."""
    kandidaten = [text]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        kandidaten.append(fence.group(1))
    a, b = text.find("{"), text.rfind("}")
    if a >= 0 and b > a:
        kandidaten.append(text[a:b + 1])
    letzter: ValueError | None = None
    for k in kandidaten:
        for variante in (k, _entschaerfen(k)):
            try:
                return json.loads(variante)
            except ValueError as e:
                letzter = e
    if a >= 0 and b > a:
        raise GraphFehler(tr("fehler.kein_json", err=letzter))
    raise GraphFehler(tr("fehler.keine_antwort"))


_ZAHL = {"type": "number"}
_LISTE = {"type": "array", "items": _ZAHL}


def _objekt(eigenschaften: dict, pflicht: list[str] | None = None) -> dict:
    o = {"type": "object", "properties": eigenschaften, "additionalProperties": False}
    if pflicht:
        o["required"] = pflicht
    return o


# JSON-Schema für Structured Outputs (output_config.format). Längen und Mindestwerte unterstützt die API dort nicht;
# die prüft danach ``bereinigen``. Die Bedeutung der Felder erklärt GRAPH_SCHEMA.
JSON_SCHEMA = _objekt({
    "name": {"type": "string"},
    "kategorie": {"type": "string", "enum": ["bett", "daybed", "sofa", "bank", "regal", "tisch", "sonstiges"]},
    "masse": _objekt({"breite": _ZAHL, "tiefe": _ZAHL, "hoehe": _ZAHL}, ["breite", "tiefe", "hoehe"]),
    "funktion": _objekt({"matratze": _LISTE, "luft": _ZAHL, "sitzhoehe": _ZAHL, "polster": _ZAHL}),
    "anker": _objekt({"liegeflaeche": _LISTE, "sitz_oben": _ZAHL}),
    "teile": {"type": "array", "items": _objekt({
        "id": {"type": "string"}, "name": {"type": "string"},
        "typ": {"type": "string", "enum": TYPEN},
        "rolle": {"type": "string", "enum": ROLLEN},
        "box": _LISTE, "anzahl": {"type": "integer"},
        "achse": {"type": "string", "enum": ["x", "y", "z"]},
        "querschnitt": _LISTE,
    }, ["id", "name", "typ", "rolle", "box"])},
}, ["name", "kategorie", "masse", "funktion", "anker", "teile"])


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
        raise GraphFehler(tr("fehler.keine_teile"))
    m = j.get("masse") if isinstance(j.get("masse"), dict) else {}
    masse = {"breite": _positiv(m.get("breite"), 1500), "tiefe": _positiv(m.get("tiefe"), 600), "hoehe": _positiv(m.get("hoehe"), 800)}

    teile = []
    for i, t in enumerate(j["teile"][:MAX_TEILE]):
        if not isinstance(t, dict):
            raise GraphFehler(tr("fehler.kein_objekt", n=i + 1))
        roh = t.get("box") if isinstance(t.get("box"), list) else []
        b = [_zahl(v) for v in roh]
        if len(b) != 6 or any(v is None for v in b):
            raise GraphFehler(tr("fehler.keine_box", n=i + 1))
        box: list[float] = []
        for k in (0, 2, 4):
            lo = max(0.0, min(1.0, min(b[k], b[k + 1])))
            hi = max(0.0, min(1.0, max(b[k], b[k + 1])))
            box += [_int_wenn_ganz(lo), _int_wenn_ganz(max(hi, lo + 0.005))]
        anzahl = _zahl(t.get("anzahl")) or 1
        qs = t.get("querschnitt")
        querschnitt = [_zahl(v) for v in qs] if isinstance(qs, list) and len(qs) == 2 else None
        typ, rolle, achse = (str(t.get(k) or "").lower() for k in ("typ", "rolle", "achse"))
        teil = {
            "id": str(t.get("id") or f"t{i + 1}")[:30],
            "name": str(t.get("name") or t.get("id") or f"Teil {i + 1}")[:40],
            "typ": typ if typ in TYPEN else "latte",
            "rolle": rolle if rolle in ROLLEN else "rahmen",
            "box": box,
            "anzahl": max(1, min(40, mm(anzahl))),
            "achse": achse if achse in ("x", "y", "z") else "x",
        }
        if querschnitt and all(v is not None for v in querschnitt):
            teil["querschnitt"] = [_int_wenn_ganz(v) for v in querschnitt]
        teile.append(teil)
    ids: set[str] = set()
    for teil in teile:
        while teil["id"] in ids:
            teil["id"] += "x"
        ids.add(teil["id"])

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
