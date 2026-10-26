"""USDZ für die AR-Ansicht: gültiges ZIP, Inhalt auf 64 Byte ausgerichtet, echte Größe in Metern, Ursprung unten mittig."""
from __future__ import annotations

import io
import re
import struct
import zipfile

from app.models.usdz import als_usda, als_usdz

MODELL = {
    "teile": [{"min": [0, 0, 0], "max": [1800, 800, 40], "ergaenzt": False},
              {"min": [0, 0, 40], "max": [40, 800, 900], "ergaenzt": True}],
    "polster": [{"min": [40, 0, 40], "max": [1800, 800, 140]}],
}


def test_zip_ausgerichtet_und_unkomprimiert():
    daten = als_usdz(MODELL)
    z = zipfile.ZipFile(io.BytesIO(daten))
    (info,) = z.infolist()
    assert info.filename == "parawerk.usda" and info.compress_type == zipfile.ZIP_STORED
    name, extra = struct.unpack_from("<HH", daten, info.header_offset + 26)
    assert (info.header_offset + 30 + name + extra) % 64 == 0
    assert z.read(info).decode().startswith("#usda 1.0")


def test_echte_groesse_und_ursprung():
    text = als_usda(MODELL)
    assert 'upAxis = "Y"' in text and "metersPerUnit = 1" in text
    zeilen = "".join(z for z in text.splitlines() if "point3f[] points" in z)
    punkte = [tuple(map(float, p)) for p in re.findall(r"\(([-\d.]+), ([-\d.]+), ([-\d.]+)\)", zeilen)]
    xs, ys, zs = zip(*punkte)
    assert (min(xs), max(xs)) == (-0.9, 0.9)  # 1,8 m breit, mittig
    assert (min(ys), max(ys)) == (0.0, 0.9)  # steht auf dem Boden, 0,9 m hoch
    assert (min(zs), max(zs)) == (-0.4, 0.4)
    for name in ("holz", "ergaenzt", "polster"):
        assert f'def Mesh "{name}"' in text and f"</Moebel/Materialien/{name}>" in text


def test_leeres_modell():
    assert "#usda 1.0" in als_usda({"teile": [], "polster": []})
