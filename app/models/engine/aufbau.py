"""Schritt 1 und 2: Bauteilgraph auf echte Maße skalieren und jedes Teil auf das Sortiment einrasten."""
from __future__ import annotations

from ..sortiment import Sortiment
from .grundlagen import AXI, AXN, Bauteil, gesetzt, mm, oder, others, zahl


def skalieren(g: dict, log: list[str]) -> list[int]:
    """Gesamtmaß über Funktionsmaße (Matratze, Sitzhöhe) bestimmen, sonst Bild-Schätzung übernehmen."""
    W, D, H = g["masse"]["breite"], g["masse"]["tiefe"], g["masse"]["hoehe"]
    f = g.get("funktion") or {}
    a = g.get("anker") or {}
    est = [W, D, H]
    if gesetzt(f.get("matratze")) and gesetzt(a.get("liegeflaeche")):
        x0, x1, y0, y1 = a["liegeflaeche"]
        luft = 10 if f.get("luft") is None else f["luft"]
        big, small = max(f["matratze"]), min(f["matratze"])
        x_long = (x1 - x0) * W >= (y1 - y0) * D
        W = (big if x_long else small) + luft
        W = W / (x1 - x0)
        D = ((small if x_long else big) + luft) / (y1 - y0)
        log.append(
            f"Liegefläche ist im Entwurf {mm((x1 - x0) * 100)} % der Breite und {mm((y1 - y0) * 100)} % der Tiefe. "
            f"Matratze {' × '.join(zahl(v) for v in f['matratze'])} mm + {zahl(luft)} mm Luft ergibt Breite {mm(W)} mm "
            f"(Bild-Schätzung {zahl(est[0])}) und Tiefe {mm(D)} mm (Schätzung {zahl(est[1])})."
        )
    if gesetzt(f.get("sitzhoehe")) and a.get("sitz_oben") is not None:
        polster = oder(f.get("polster"), 0)
        H = (f["sitzhoehe"] - polster) / a["sitz_oben"]
        log.append(
            f"Sitzhöhe {zahl(f['sitzhoehe'])} mm minus {zahl(polster)} mm Polster: Sitzfläche liegt bei "
            f"{zahl(f['sitzhoehe'] - polster)} mm. Im Entwurf ist das {mm(a['sitz_oben'] * 100)} % der Höhe, "
            f"also Gesamthöhe {mm(H)} mm (Schätzung {zahl(est[2])})."
        )
    if not log:
        log.append(f"Keine Funktionsmaße: Bild-Schätzung {zahl(W)} × {zahl(D)} × {zahl(H)} mm wird übernommen.")
    return [mm(W), mm(D), mm(H)]


def querschnitt_einrasten(S: Sortiment, typ: str, tgt: dict, cross: list[int], hint) -> dict:
    """Nächsten Querschnitt aus dem Sortiment wählen. ``tgt``: Zielmaß je Querachse (None = unbekannt)."""
    if typ in ("latte", "kantholz"):
        best = None
        for p in S[typ]:
            for s1, s2 in ((p["a"], p["b"]), (p["b"], p["a"])):
                sz = {cross[0]: s1, cross[1]: s2}
                cost = 0
                for c in cross:
                    cost += 0 if tgt.get(c) is None else abs(sz[c] - tgt[c])
                if gesetzt(hint) and sorted(zahl(v) for v in (p["a"], p["b"])) == sorted(zahl(v) for v in hint):
                    cost -= 15
                if best is None or cost < best["cost"]:
                    best = {"cost": cost, "sz": sz, "prof": {"label": p["label"], "a": p["a"], "b": p["b"]}}
        return best
    # Brett oder Platte aus Leimholz: dünnere Querachse = Stärke
    c1, c2 = cross
    t1 = 1e9 if tgt.get(c1) is None else tgt[c1]
    t2 = 1e9 if tgt.get(c2) is None else tgt[c2]
    t_ax = c1 if t1 <= t2 else c2
    w_ax = c2 if t_ax == c1 else c1
    want = tgt.get(t_ax)
    staerken = [p["t"] for p in S["leimholz"]]
    t = staerken[0]
    if want is not None:
        for b in staerken[1:]:
            if abs(b - want) < abs(t - want):
                t = b
    w = mm(tgt[w_ax])
    return {"sz": {t_ax: t, w_ax: w}, "prof": {"t": t, "w": w}, "t_ax": t_ax, "w_ax": w_ax}


def aufbauen(S: Sortiment, g: dict, dims: list[int], log: list[str]) -> tuple[list[Bauteil], dict]:
    """Jede Teilgruppe des Graphen in einzelne Bauteile mit Sortiments-Querschnitt umsetzen."""
    W, D, H = dims
    members: list[Bauteil] = []
    groups: dict = {}
    for p in g["teile"]:
        box = p["box"]
        rmin = [box[0] * W, box[2] * D, box[4] * H]
        rmax = [box[1] * W, box[3] * D, box[5] * H]
        n = max(1, mm(oder(p.get("anzahl"), 1)))
        dax = AXI.get(p.get("achse"), 0) if n > 1 else -1
        exts = [rmax[a] - rmin[a] for a in (0, 1, 2)]
        cand = [a for a in (0, 1, 2) if a != dax]
        long = cand[0]
        for b in cand[1:]:
            if exts[b] > exts[long]:
                long = b
        cross = others(long)
        tgt: dict = {c: (None if c == dax else exts[c]) for c in cross}
        hint = p.get("querschnitt")
        if gesetzt(hint) and dax >= 0:  # Hinweis auf die Querachsen verteilen
            known = next(c for c in cross if c != dax)
            h1, h2 = hint if abs(hint[0] - exts[known]) <= abs(hint[1] - exts[known]) else [hint[1], hint[0]]
            tgt[dax] = h2
        if dax >= 0 and tgt.get(dax) is None:
            tgt[dax] = exts[dax] / n * 0.85
        sn = querschnitt_einrasten(S, p["typ"], tgt, cross, hint)
        typ = "brett" if p["typ"] == "platte" else p["typ"]
        name = oder(p.get("name"), p["id"])
        gelesen = "×".join(str(mm(tgt[c])) for c in cross)
        bekommen = "×".join(zahl(sn["sz"][c]) for c in cross)
        profil = f"Leimholz {zahl(sn['prof']['t'])} mm, {zahl(sn['prof']['w'])} mm breit" if typ == "brett" else sn["prof"]["label"]
        stueck = f", {n} Stück entlang {AXN[dax]}" if n > 1 else ""
        log.append(f"{name}: gelesen ca. {gelesen} mm → {profil} ({bekommen}){stueck}")
        for i in range(n):
            mn, mx = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
            for a in (0, 1, 2):
                if a == long:
                    mn[a], mx[a] = rmin[a], rmax[a]
                    continue
                s = sn["sz"][a]
                if a == dax:
                    L = rmax[a] - rmin[a]
                    mn[a] = rmin[a] + (L - s) / 2 if n == 1 else rmin[a] + i * (L - s) / (n - 1)
                else:
                    lo, hi = box[a * 2], box[a * 2 + 1]
                    mn[a] = rmin[a] if lo <= 0.015 else rmax[a] - s if hi >= 0.985 else (rmin[a] + rmax[a] - s) / 2
                mx[a] = mn[a] + s
            members.append(Bauteil(
                id=f"{p['id']}-{i + 1}" if n > 1 else p["id"], part=p["id"], name=name, typ=typ, rolle=p.get("rolle"),
                prof=sn["prof"], long=long, dax=dax, min=mn, max=mx, origin="entwurf",
            ))
        if n > 1:
            groups[p["id"]] = {"dax": dax, "n": n}
    return members, groups
