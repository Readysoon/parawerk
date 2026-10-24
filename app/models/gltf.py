"""3D-Modell als glTF-Binärdatei (.glb), damit die App es ohne eigene 3D-Logik anzeigen kann.

Jedes Teil ist ein Quader. Drei Materialien: Holz aus dem Entwurf, für Stabilität ergänzt (orange), Polster.
Engine-Koordinaten in mm (x Breite, y Tiefe von vorne nach hinten, z Höhe) werden zu glTF in Metern mit
Y nach oben: X = x, Y = z, Z = -y (vorne zeigt zum Betrachter).
"""
from __future__ import annotations

import json
import struct

FARBEN = {"holz": (0.85, 0.76, 0.63, 1.0), "ergaenzt": (0.76, 0.25, 0.05, 1.0), "polster": (0.79, 0.81, 0.84, 1.0)}
# 6 Seiten je Quader: Normale und die vier Ecken (Indizes in die 8 Ecken, gegen den Uhrzeigersinn von außen)
SEITEN = [
    ((1, 0, 0), (1, 5, 7, 3)), ((-1, 0, 0), (4, 0, 2, 6)),
    ((0, 1, 0), (2, 3, 7, 6)), ((0, -1, 0), (4, 5, 1, 0)),
    ((0, 0, 1), (0, 1, 3, 2)), ((0, 0, -1), (5, 4, 6, 7)),
]


def _ecken(mn: list[float], mx: list[float]) -> list[tuple[float, float, float]]:
    """8 Ecken in glTF-Koordinaten; Bit 0 = x, Bit 1 = Höhe, Bit 2 = Tiefe."""
    out = []
    for i in range(8):
        x = mx[0] if i & 1 else mn[0]
        h = mx[2] if i & 2 else mn[2]
        y = mx[1] if i & 4 else mn[1]
        out.append((x / 1000, h / 1000, -y / 1000))
    return out


def _gitter(quader: list[tuple[list[float], list[float]]]) -> tuple[bytes, bytes, bytes, int, int, list, list]:
    pos, nor, idx = [], [], []
    for mn, mx in quader:
        e = _ecken(mn, mx)
        for n, (a, b, c, d) in SEITEN:
            basis = len(pos)
            for k in (a, b, c, d):
                pos.append(e[k])
                nor.append(n)
            idx += [basis, basis + 1, basis + 2, basis, basis + 2, basis + 3]
    lo = [min(p[i] for p in pos) for i in range(3)]
    hi = [max(p[i] for p in pos) for i in range(3)]
    return (struct.pack(f"<{3 * len(pos)}f", *[v for p in pos for v in p]),
            struct.pack(f"<{3 * len(nor)}f", *[v for p in nor for v in p]),
            struct.pack(f"<{len(idx)}I", *idx), len(pos), len(idx), lo, hi)


def _auffuellen(b: bytes, mit: bytes = b"\0") -> bytes:
    return b + mit * (-len(b) % 4)


def als_glb(modell: dict) -> bytes:
    """``modell`` wie von ``views.praesentation.modell_3d``: teile (min, max, ergaenzt), polster (min, max)."""
    gruppen: dict[str, list] = {"holz": [], "ergaenzt": [], "polster": []}
    for teil in modell.get("teile", []):
        gruppen["ergaenzt" if teil.get("ergaenzt") else "holz"].append((teil["min"], teil["max"]))
    for p in modell.get("polster", []):
        gruppen["polster"].append((p["min"], p["max"]))

    puffer = b""
    views, accessors, primitives, materials = [], [], [], []

    def view(daten: bytes, ziel: int) -> int:
        nonlocal puffer
        views.append({"buffer": 0, "byteOffset": len(puffer), "byteLength": len(daten), "target": ziel})
        puffer = _auffuellen(puffer + daten)
        return len(views) - 1

    for name, quader in gruppen.items():
        if not quader:
            continue
        p, n, i, anzahl, anzahl_idx, lo, hi = _gitter(quader)
        accessors.append({"bufferView": view(p, 34962), "componentType": 5126, "count": anzahl, "type": "VEC3",
                          "min": lo, "max": hi})
        accessors.append({"bufferView": view(n, 34962), "componentType": 5126, "count": anzahl, "type": "VEC3"})
        accessors.append({"bufferView": view(i, 34963), "componentType": 5125, "count": anzahl_idx, "type": "SCALAR"})
        materials.append({"name": name, "pbrMetallicRoughness": {"baseColorFactor": list(FARBEN[name]),
                                                                  "metallicFactor": 0.0, "roughnessFactor": 0.85}})
        a = len(accessors)
        primitives.append({"attributes": {"POSITION": a - 3, "NORMAL": a - 2}, "indices": a - 1,
                           "material": len(materials) - 1})

    gltf = {
        "asset": {"version": "2.0", "generator": "Parawerk"},
        "scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0, "name": "Moebel"}],
        "meshes": [{"primitives": primitives}], "materials": materials,
        "buffers": [{"byteLength": len(puffer)}], "bufferViews": views, "accessors": accessors,
    }
    teil_json = _auffuellen(json.dumps(gltf, separators=(",", ":")).encode(), b" ")
    teil_bin = _auffuellen(puffer)
    laenge = 12 + 8 + len(teil_json) + 8 + len(teil_bin)
    return (struct.pack("<III", 0x46546C67, 2, laenge)
            + struct.pack("<II", len(teil_json), 0x4E4F534A) + teil_json
            + struct.pack("<II", len(teil_bin), 0x004E4942) + teil_bin)
