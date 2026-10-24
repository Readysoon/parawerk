"""Entwürfe-Controller: Foto + Maske + Wunsch → Entwürfe der Bild-KI."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..config import Einstellungen, einstellungen
from ..i18n import t
from ..services.bild_ki import BildKI
from ..services.fehler import DienstFehler, NichtVerfuegbar
from ..services.konstrukteur import Konstrukteur
from ..services.kostendeckel import Kostendeckel, Kunde
from ..services.prompts import bearbeitung_prompt, inpaint_prompt
from .abhaengigkeiten import bild_ki, konstrukteur, kostendeckel, kunde
from .kontingent import erstatten, reservieren
from .schemas import EntwuerfeAnfrage, EntwuerfeAntwort, NachjustierenAnfrage, NachjustierenAntwort

router = APIRouter(prefix="/api", tags=["Entwürfe"])


@router.post("/entwuerfe", response_model=EntwuerfeAntwort)
async def entwuerfe(
    anfrage: EntwuerfeAnfrage,
    ki: BildKI = Depends(bild_ki),
    k: Konstrukteur = Depends(konstrukteur),
    e: Einstellungen = Depends(einstellungen),
    deckel: Kostendeckel = Depends(kostendeckel),
    kd: Kunde = Depends(kunde),
) -> EntwuerfeAntwort:
    if not ki.demo and not (anfrage.foto and anfrage.maske):
        raise HTTPException(400, t("fehler.foto_maske"))
    eintrag = None if ki.demo else await reservieren(deckel, "runde", kd)
    prompt = inpaint_prompt(anfrage.wunsch)
    if not ki.demo:  # nur wenn wirklich gemalt wird: Claude schreibt den Prompt mit Blick auf Foto und Maske
        try:
            prompt = await k.bild_prompt(anfrage.wunsch, anfrage.foto, anfrage.maske)
        except DienstFehler:
            pass  # dann eben der wörtliche Wunsch
    seeds = [secrets.randbelow(10**9) for _ in range(e.anzahl_entwuerfe)]
    try:
        bilder = await ki.entwerfen(anfrage.foto or "", anfrage.maske or "", prompt, seeds)
    except DienstFehler as err:
        await erstatten(deckel, eintrag)
        raise HTTPException(502, t("fehler.entwuerfe", err=err)) from err
    return EntwuerfeAntwort(demo=ki.demo, prompt=prompt, bilder=bilder)


@router.post("/entwuerfe/nachjustieren", response_model=NachjustierenAntwort)
async def nachjustieren(
    anfrage: NachjustierenAnfrage,
    ki: BildKI = Depends(bild_ki),
    k: Konstrukteur = Depends(konstrukteur),
    deckel: Kostendeckel = Depends(kostendeckel),
    kd: Kunde = Depends(kunde),
) -> NachjustierenAntwort:
    """Gewählten Entwurf per Text ändern (FLUX Kontext). Die App setzt danach wieder nur den markierten Bereich ein."""
    eintrag = None if ki.demo else await reservieren(deckel, "nachjustieren", kd)
    try:
        prompt = await k.bearbeitungs_prompt(anfrage.wunsch, anfrage.anpassung, anfrage.bild)
    except DienstFehler:
        prompt = bearbeitung_prompt(anfrage.anpassung)
    try:
        bild = await ki.bearbeiten(anfrage.bild, prompt, secrets.randbelow(10**9))
    except NichtVerfuegbar as err:
        raise HTTPException(501, str(err)) from err
    except DienstFehler as err:
        await erstatten(deckel, eintrag)
        raise HTTPException(502, t("fehler.nachjustieren", err=err)) from err
    return NachjustierenAntwort(prompt=prompt, bild=bild)
