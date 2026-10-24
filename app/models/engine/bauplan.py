"""Schritt 6: Bauplan aus dem fertigen Modell: Einkaufsliste, Zuschnitt, Schrauben, Montagefolge."""
from __future__ import annotations

import math

from ...i18n import dez, holz
from ...i18n import t as tr
from ..sortiment import SCHNITT_PREIS, Sortiment
from .grundlagen import sitzteile, SLATS, Bauteil, eintraege, ext, fest, gesetzt, mm, prio, zahl

SAEGESCHNITT = 3  # mm


def stangen_packen(pieces: list[dict], stock: list[int], kerf: int) -> list[dict]:
    """Stablängen auf Handelslängen verteilen (First Fit Decreasing)."""
    bins: list[dict] = []
    max_s = max(stock)
    for p in sorted(pieces, key=lambda p: -p["len"]):
        if p["len"] > max_s:
            bins.append({"used": p["len"], "items": [p], "L": p["len"], "too_long": True})
            continue
        b = next((b for b in bins if b["used"] + (kerf if b["items"] else 0) + p["len"] <= max_s), None)
        if b is None:
            b = {"used": 0, "items": []}
            bins.append(b)
        b["used"] += (kerf if b["items"] else 0) + p["len"]
        b["items"].append(p)
    for b in bins:
        if not b.get("too_long"):
            b["L"] = min(s for s in stock if s >= b["used"])
    return bins


def streifen_packen(items: list[dict], L: int, Wd: int, kerf: int) -> list[dict]:
    """Bretter in Streifen auf Leimholzplatten verteilen."""
    sheets: list[dict] = []
    for it in sorted(items, key=lambda a: (-a["w"], -a["l"])):
        ok = False
        for s in sheets:
            for st in s["strips"]:
                if it["w"] <= st["h"] and st["used"] + it["l"] <= L:
                    st["items"].append({**it, "x": st["used"], "y": st["y"]})
                    st["used"] += it["l"] + kerf
                    ok = True
                    break
            if ok:
                break
            if s["used_h"] + it["w"] <= Wd:
                s["strips"].append({"y": s["used_h"], "h": it["w"], "used": it["l"] + kerf,
                                    "items": [{**it, "x": 0, "y": s["used_h"]}]})
                s["used_h"] += it["w"] + kerf
                ok = True
                break
        if not ok:
            sheets.append({"used_h": it["w"] + kerf,
                           "strips": [{"y": 0, "h": it["w"], "used": it["l"] + kerf, "items": [{**it, "x": 0, "y": 0}]}]})
    return sheets


MONTAGE = [  # Rollen je Montageschritt, Text unter montage.<n> im Sprachkatalog
    (("bein", "pfosten", "kufe", "stuetze"), "montage.1"),
    (("rahmen", "zarge"), "montage.2"),
    (("auflage", "mittelsteg", "querriegel"), "montage.3"),
    (("lattenrost", "sitzflaeche", "liegeflaeche", "regalboden"), "montage.4"),
    (("lehne",), "montage.5"),
    (("verkleidung",), "montage.6"),
]


def bauplan(S: Sortiment, ms: list[Bauteil], J: list[dict]) -> dict:
    kerf = SAEGESCHNITT
    lines: list[dict] = []
    cut_groups: list[dict] = []
    cuts = 0

    # Stäbe
    by_prof: dict = {}
    for m in ms:
        if m.typ != "brett":
            by_prof.setdefault(m.prof["label"], []).append({"len": mm(ext(m, m.long)), "name": m.name, "id": m.id})
    for label, ps in eintraege(by_prof):
        typ = "latte" if any(p["label"] == label for p in S["latte"]) else "kantholz"
        stock = next(p for p in S[typ] if p["label"] == label)["L"]
        bins = stangen_packen(ps, stock, kerf)
        by_l: dict = {}
        for b in bins:
            by_l[b["L"]] = by_l.get(b["L"], 0) + 1
        for L, n in eintraege(by_l):
            lines.append({"n": n, "text": tr("plan.stab", holz=holz(label), laenge=dez(fest(L / 1000, 1)))})
        for b in bins:
            cuts += len(b["items"]) - (1 if b["used"] == b["L"] else 0)
        cut_groups.append({"label": holz(label), "kind": "stab", "bins": bins})

    # Leimholz
    by_t: dict = {}
    for m in ms:
        if m.typ == "brett":
            t = m.prof["t"]
            dims = sorted((mm(ext(m, a)) for a in (0, 1, 2) if mm(ext(m, a)) != t), reverse=True)
            by_t.setdefault(t, []).append({"l": dims[0] if dims else t, "w": dims[1] if len(dims) > 1 else t,
                                           "name": m.name, "id": m.id})
    for t, items in eintraege(by_t):
        opt = next(p for p in S["leimholz"] if p["t"] == t)
        best = None
        for Wd in opt["W"]:
            if any(i["w"] > Wd for i in items):
                continue
            sheets = streifen_packen(items, opt["L"], Wd, kerf)
            area = len(sheets) * Wd
            if best is None or area < best["area"] or (area == best["area"] and len(sheets) < len(best["sheets"])):
                best = {"Wd": Wd, "sheets": sheets, "area": area}
        if best is None:
            lines.append({"n": 0, "text": tr("plan.verleimen", t=zahl(t))})
            continue
        lines.append({"n": len(best["sheets"]), "text": tr("plan.leimholz", t=zahl(t), l=zahl(opt["L"] / 10), w=zahl(best["Wd"] / 10))})
        for s in best["sheets"]:
            cuts += len(s["strips"]) + sum(len(st["items"]) for st in s["strips"]) - 1
        cut_groups.append({"label": tr("plan.leimholz_gruppe", t=zahl(t), l=zahl(opt["L"]), w=zahl(best["Wd"])), "kind": "platte",
                           "L": opt["L"], "W": best["Wd"], "sheets": best["sheets"]})

    # Schrauben
    scr: dict = {}
    for j in J:
        if max(prio(j["a"]), prio(j["b"])) < 4:
            continue  # Latte an Latte wird nicht verschraubt
        ts = [j["a"].typ, j["b"].typ]
        if all(t == "kantholz" for t in ts):
            k = "Holzschraube 6×100 (Rahmen)"
        elif "brett" in ts:
            k = "Holzschraube 4×40"
        else:
            k = "Holzschraube 4×50"
        scr[k] = scr.get(k, 0) + 2
    hardware = [{"n": math.ceil(v * 1.1), "text": tr(f"schraube.{k}")} for k, v in eintraege(scr)]

    steps = [{"t": tr(key), "n": sum(1 for m in ms if m.rolle in rollen)} for rollen, key in MONTAGE]
    steps = [s for s in steps if s["n"]]
    return {"lines": lines, "cut_groups": cut_groups, "cuts": cuts, "cost": cuts * SCHNITT_PREIS,
            "hardware": hardware, "steps": steps}


def polster(g: dict, ms: list[Bauteil], dims: list[int]) -> list[dict]:
    """Matratze und Polster, nur zur Darstellung."""
    f = g.get("funktion") or {}
    soft: list[dict] = []
    if gesetzt(f.get("matratze")):
        slats = [m for m in ms if m.rolle in SLATS]
        if not slats:
            return soft
        top = max(m.max[2] for m in slats)
        a = g["anker"]["liegeflaeche"]
        c = [(a[0] + a[1]) / 2 * dims[0], (a[2] + a[3]) / 2 * dims[1]]
        big, small = max(f["matratze"]), min(f["matratze"])
        x_long = (a[1] - a[0]) * dims[0] >= (a[3] - a[2]) * dims[1]
        w, d = (big, small) if x_long else (small, big)
        soft.append({"min": [c[0] - w / 2, c[1] - d / 2, top], "max": [c[0] + w / 2, c[1] + d / 2, top + 160]})
    if gesetzt(f.get("polster")):
        seat = sitzteile(ms)
        if not seat:
            return soft
        mn = [min(m.min[a] for m in seat) for a in (0, 1)]
        mx = [max(m.max[a] for m in seat) for a in (0, 1)]
        top = max(m.max[2] for m in seat)
        soft.append({"min": [mn[0] + 10, mn[1] + 5, top], "max": [mx[0] - 10, mx[1] - 5, top + f["polster"]]})
    return soft
