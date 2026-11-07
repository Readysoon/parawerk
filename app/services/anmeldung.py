"""ID-Tokens von „Mit Apple anmelden“ und „Mit Google anmelden“ prüfen.

Beide Anbieter signieren ein JWT mit ihren öffentlichen Schlüsseln (JWKS). Geprüft wird: Signatur, Aussteller,
Empfänger (unsere Client-IDs: App und Website) und Ablauf. Die Schlüssel werden zwischengespeichert.
"""
from __future__ import annotations

from dataclasses import dataclass

import jwt

ANBIETER = {
    "apple": {"jwks": "https://appleid.apple.com/auth/keys", "iss": ("https://appleid.apple.com",)},
    "google": {"jwks": "https://www.googleapis.com/oauth2/v3/certs",
               "iss": ("https://accounts.google.com", "accounts.google.com")},
}
_clients: dict[str, jwt.PyJWKClient] = {}


class AnmeldeFehler(Exception):
    pass


@dataclass(frozen=True)
class Identitaet:
    anbieter: str
    sub: str
    email: str | None


def pruefen(anbieter: str, id_token: str, client_ids: list[str]) -> Identitaet:
    """ID-Token prüfen und die Nutzer-ID zurückgeben. Wirft ``AnmeldeFehler``, wenn etwas nicht stimmt."""
    if anbieter not in ANBIETER:
        raise AnmeldeFehler("unbekannter Anbieter")
    if not client_ids:
        raise AnmeldeFehler(f"{anbieter} ist nicht eingerichtet")
    a = ANBIETER[anbieter]
    try:
        client = _clients.setdefault(anbieter, jwt.PyJWKClient(a["jwks"], cache_keys=True, lifespan=3600))
        schluessel = client.get_signing_key_from_jwt(id_token).key
        daten = jwt.decode(id_token, schluessel, algorithms=["RS256"], audience=client_ids,
                           options={"require": ["iss", "sub", "aud", "exp"]}, leeway=60)
    except jwt.PyJWTError as err:
        raise AnmeldeFehler(str(err)) from err
    if daten.get("iss") not in a["iss"]:
        raise AnmeldeFehler("falscher Aussteller")
    email = daten.get("email")
    if anbieter == "google" and not daten.get("email_verified", False):
        email = None
    return Identitaet(anbieter, str(daten["sub"]), email if isinstance(email, str) else None)
