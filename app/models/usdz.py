"""3D-Modell als USDZ für die AR-Ansicht auf dem iPhone (AR Quick Look): das Möbel in echter Größe im Zimmer.

USDZ ist ein unkomprimiertes ZIP mit einer USD-Datei; jede Datei darin muss auf 64 Byte ausgerichtet beginnen.
Die Szene ist Text (USDA), in Metern mit Y nach oben. Der Ursprung liegt unten in der Mitte des Möbels,
damit AR Quick Look es sauber auf den Boden stellt.
"""
from __future__ import annotations

import io
import struct
import zipfile

from .gltf import FARBEN, SEITEN, _ecken


def _zahl(v: float) -> str:
    return f"{v:.4f}".rstrip("0").rstrip(".") if v else "0"


def _liste(werte) -> str:
    return ", ".join(f"({_zahl(a)}, {_zahl(b)}, {_zahl(c)})" for a, b, c in werte)


def _mesh(name: str, quader: list[tuple[list[float], list[float]]], versatz: tuple[float, float, float]) -> str:
    punkte, normalen, indizes = [], [], []
    for mn, mx in quader:
        ecken = [(x - versatz[0], y - versatz[1], z - versatz[2]) for x, y, z in _ecken(mn, mx)]
        for n, seite in SEITEN:
            basis = len(punkte)
            for k in seite:
                punkte.append(ecken[k])
                normalen.append(n)
            indizes += [basis, basis + 1, basis + 2, basis + 3]
    return f'''
    def Mesh "{name}" (
        prepend apiSchemas = ["MaterialBindingAPI"]
    )
    {{
        int[] faceVertexCounts = [{", ".join(["4"] * (len(indizes) // 4))}]
        int[] faceVertexIndices = [{", ".join(map(str, indizes))}]
        point3f[] points = [{_liste(punkte)}]
        normal3f[] normals = [{_liste(normalen)}] (
            interpolation = "vertex"
        )
        uniform token subdivisionScheme = "none"
        rel material:binding = </Moebel/Materialien/{name}>
    }}
'''


def _material(name: str) -> str:
    r, g, b, _ = FARBEN[name]
    return f'''
        def Material "{name}"
        {{
            token outputs:surface.connect = </Moebel/Materialien/{name}/Oberflaeche.outputs:surface>

            def Shader "Oberflaeche"
            {{
                uniform token info:id = "UsdPreviewSurface"
                color3f inputs:diffuseColor = ({_zahl(r)}, {_zahl(g)}, {_zahl(b)})
                float inputs:metallic = 0
                float inputs:roughness = 0.85
                token outputs:surface
            }}
        }}
'''


def als_usda(modell: dict) -> str:
    """``modell`` wie für ``als_glb``: teile (min, max, ergaenzt), polster (min, max), in mm."""
    gruppen: dict[str, list] = {"holz": [], "ergaenzt": [], "polster": []}
    for teil in modell.get("teile", []):
        gruppen["ergaenzt" if teil.get("ergaenzt") else "holz"].append((teil["min"], teil["max"]))
    for p in modell.get("polster", []):
        gruppen["polster"].append((p["min"], p["max"]))
    gruppen = {name: q for name, q in gruppen.items() if q}
    ecken = [e for g in gruppen.values() for mn, mx in g for e in _ecken(mn, mx)]
    if ecken:
        lo = [min(e[i] for e in ecken) for i in range(3)]
        hi = [max(e[i] for e in ecken) for i in range(3)]
        versatz = ((lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2)  # unten in der Mitte
    else:
        versatz = (0.0, 0.0, 0.0)
    meshes = "".join(_mesh(name, q, versatz) for name, q in gruppen.items())
    materialien = "".join(_material(name) for name in gruppen)
    return f'''#usda 1.0
(
    defaultPrim = "Moebel"
    metersPerUnit = 1
    upAxis = "Y"
)

def Xform "Moebel" (
    kind = "component"
)
{{{meshes}
    def Scope "Materialien"
    {{{materialien}    }}
}}
'''


def als_usdz(modell: dict) -> bytes:
    return _zip({"parawerk.usda": als_usda(modell).encode()})


def _zip(dateien: dict[str, bytes]) -> bytes:
    """Unkomprimiertes ZIP, Dateiinhalte auf 64 Byte ausgerichtet (Vorgabe von USDZ)."""
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_STORED) as z:
        for name, daten in dateien.items():
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            kopf = puffer.tell() + 30 + len(name.encode()) + 4  # lokaler Kopf + Name + Kopf des Füllfelds
            luecke = -kopf % 64
            info.extra = struct.pack("<HH", 0x1986, luecke) + b"\0" * luecke
            z.writestr(info, daten)
    return puffer.getvalue()
