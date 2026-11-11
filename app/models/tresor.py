"""Fotos und Bilder verschlüsselt in der Datenbank ablegen (AES-256-GCM).

Der Schlüssel steht nur in ``DATEN_SCHLUESSEL`` (fly secret bzw. .env), nie in der Datenbank. Wer die Datenbank,
einen fly-Schnappschuss oder eine Sicherung erwischt, sieht ohne den Schlüssel nur Zufallsbytes.

Anders als Passwörter (die nur gehasht werden, man braucht sie nie zurück) müssen Fotos wieder lesbar sein: die
Bild-KI und Claude brauchen sie, und die App zeigt sie an. Deshalb verschlüsseln statt hashen.

- Ohne Schlüssel (lokal) wird unverschlüsselt gespeichert.
- Alte, unverschlüsselte Einträge bleiben lesbar (erkennbar am fehlenden Vorspann).
- Schlüssel verloren = verschlüsselte Bilder verloren. Deshalb zusätzlich im Passwortmanager aufheben.
- Neuen Schlüssel erzeugen: ``python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"``
"""
from __future__ import annotations

import base64
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VORSPANN = b"PWv1"  # Version 1: AES-256-GCM, 12 Byte Nonce


class SchluesselFehlt(RuntimeError):
    pass


@lru_cache
def _schluessel() -> bytes | None:
    from ..config import Einstellungen
    roh = Einstellungen().daten_schluessel.strip()
    if not roh:
        return None
    k = base64.b64decode(roh)
    if len(k) != 32:
        raise ValueError("DATEN_SCHLUESSEL muss 32 Byte (base64) sein")
    return k


def zu(daten: bytes) -> bytes:
    """Verschlüsseln (ohne Schlüssel: unverändert)."""
    k = _schluessel()
    if k is None:
        return daten
    nonce = os.urandom(12)
    return VORSPANN + nonce + AESGCM(k).encrypt(nonce, daten, VORSPANN)


def auf(daten: bytes | None) -> bytes | None:
    """Entschlüsseln; unverschlüsselte (alte) Daten kommen unverändert zurück."""
    if daten is None:
        return None
    daten = bytes(daten)
    if not daten.startswith(VORSPANN):
        return daten
    k = _schluessel()
    if k is None:
        raise SchluesselFehlt("verschlüsseltes Bild, aber DATEN_SCHLUESSEL fehlt")
    n = len(VORSPANN)
    return AESGCM(k).decrypt(daten[n:n + 12], daten[n + 12:], VORSPANN)
