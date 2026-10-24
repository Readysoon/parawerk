"""Schritt 5: Endkontrolle des fertigen Modells (Halt, Spannweiten, Stand, Wackeln, Funktion, Bereich)."""
from __future__ import annotations

import math

from .grundlagen import sitzteile, LOADED, SLATS, Bauteil, cen, einmalig, ext, gesetzt, max_or, min_or, mm, oder, zahl
from ...i18n import t, und
from .reparatur import aussteifung, max_spannweite, spannweite


def endkontrolle(ms: list[Bauteil], g: dict, bereich: list[float] | None, J: list[dict]) -> dict:
    out: list[dict] = []
    extra: dict = {}
    bb = {"min": [min(m.min[a] for m in ms) for a in (0, 1, 2)], "max": [max(m.max[a] for m in ms) for a in (0, 1, 2)]}
    dims = [mm(bb["max"][a] - bb["min"][a]) for a in (0, 1, 2)]

    # Halt
    loose = [m for m in ms if not any(j["a"] is m or j["b"] is m for j in J)]
    if loose:
        out.append({"ok": False, "t": t("chk.lose", n=len(loose), namen=", ".join(einmalig(m.name for m in loose)))})
    else:
        out.append({"ok": True, "t": t("chk.verbunden")})

    # Spannweiten
    worst_ratio, worst_m = 0, None
    for m in ms:
        if m.rolle not in LOADED or m.long == 2:
            continue
        si = spannweite(m, J)
        if not si["supported"]:
            worst_ratio, worst_m = 9, m
            continue
        r = si["worst"]["len"] / max_spannweite(m)
        if r > worst_ratio:
            worst_ratio, worst_m = r, m
    if worst_ratio <= 1:
        out.append({"ok": True, "t": t("chk.spann_ok", p=mm(worst_ratio * 100))})
    elif worst_ratio == 9:
        out.append({"ok": False, "t": t("chk.liegt_nicht", name=worst_m.name)})
    else:
        out.append({"ok": False, "t": t("chk.spann", name=worst_m.name, p=mm(worst_ratio * 100))})

    # Stand
    floor = [m for m in ms if m.min[2] <= 0.5]

    def vol(m: Bauteil) -> float:
        return ext(m, 0) * ext(m, 1) * ext(m, 2)

    V = 0
    for m in ms:
        V = V + vol(m)
    cg = []
    for a in (0, 1):
        s = 0
        for m in ms:
            s = s + vol(m) * cen(m, a)
        cg.append(s / V)
    fp_min = [min_or(m.min[a] for m in floor) for a in (0, 1)]
    fp_max = [max_or(m.max[a] for m in floor) for a in (0, 1)]
    inside = len(floor) >= 3 and all(fp_min[a] < c < fp_max[a] for a, c in enumerate(cg))
    wall = any(m.rolle == "wandleiste" for m in ms)
    if wall and len(floor) >= 1:
        out.append({"ok": True, "t": t("chk.wand", n=len(floor))})
    elif inside:
        out.append({"ok": True, "t": t("chk.stand", n=len(floor))})
    else:
        out.append({"ok": False, "t": t("chk.stand_nein")})
    if dims[2] > 1.5 * min(dims[0], dims[1]):
        out.append({"ok": None, "t": t("chk.hoch")})

    # Wackeln
    br = aussteifung(ms, J)
    if all(b["ok"] for b in br):
        out.append({"ok": True, "t": t("chk.wackelt_nicht", x=br[0]["why"], y=br[1]["why"])})
    else:
        wo = und([t("wort.seitlich") if b["ax"] == 0 else t("wort.vorne_hinten") for b in br if not b["ok"]])
        out.append({"ok": False, "t": t("chk.wackelt", wo=wo)})

    # Funktion
    f = g.get("funktion") or {}
    if gesetzt(f.get("matratze")):
        slats = [m for m in ms if m.rolle in SLATS]
        top = max(m.max[2] for m in slats) if slats else 0
        walls = [m for m in ms if m.max[2] > top + 15 and m.min[2] < top + 60]
        a = g["anker"]["liegeflaeche"]
        c = [(a[0] + a[1]) / 2 * dims[0], (a[2] + a[3]) / 2 * dims[1]]
        x_long = (a[1] - a[0]) * dims[0] >= (a[3] - a[2]) * dims[1]
        mat = [max(f["matratze"]), min(f["matratze"])] if x_long else [min(f["matratze"]), max(f["matratze"])]
        clear = []
        for ax in (0, 1):
            o = 1 - ax
            ws = [m for m in walls if m.max[o] >= c[o] - mat[o] / 2 - 1 and m.min[o] <= c[o] + mat[o] / 2 + 1]
            left = max_or(m.max[ax] for m in ws if m.max[ax] <= c[ax])
            right = min_or(m.min[ax] for m in ws if m.min[ax] >= c[ax])
            clear.append(mm(right - left) if math.isfinite(left) and math.isfinite(right) else None)
        ok = all(v is None or (v >= mat[i] and v - mat[i] <= 40) for i, v in enumerate(clear))
        extra["clear"], extra["mat"] = clear, mat
        offen = t("wort.offen")
        innen = " × ".join(offen if v is None else str(v) for v in clear)
        luft = t("chk.luft", werte=" / ".join(offen if v is None else zahl(v - mat[i]) for i, v in enumerate(clear))) if ok else ""
        out.append({"ok": ok, "t": t("chk.liegeflaeche", innen=innen, mat=" × ".join(zahl(v) for v in mat), luft=luft, top=mm(top))})
    if gesetzt(f.get("sitzhoehe")):
        seat = sitzteile(ms)
        top = max(m.max[2] for m in seat) if seat else 0
        polster = oder(f.get("polster"), 0)
        sh = mm(top + polster)
        extra["seat"] = sh
        lounge = f["sitzhoehe"] < 360
        ok = 260 <= sh <= 360 if lounge else 400 <= sh <= 480
        out.append({"ok": ok, "t": t("chk.sitz", polster=zahl(polster), sh=sh, ziel=zahl(f["sitzhoehe"]),
                                     bereich=t("wort.lounge") if lounge else t("wort.stuhl"))})
    if bereich is not None:
        fits = dims[0] <= bereich[0] and dims[1] <= bereich[1] and dims[2] <= bereich[2]
        out.append({"ok": fits, "t": t("chk.bereich", dims=" × ".join(map(str, dims)), bereich=" × ".join(zahl(v) for v in bereich),
                                       ergebnis=t("wort.passt") if fits else t("wort.passt_nicht"))})
    return {"checks": out, "dims": dims, "bb": bb, **extra}
