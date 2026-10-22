"""Entwürfe-Controller: Foto + Maske + Wunsch → Entwürfe der Bild-KI."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, Depends, HTTPException

from ..config import Einstellungen, einstellungen
from ..services.bild_ki import BildKI
from ..services.fehler import DienstFehler
from ..services.konstrukteur import Konstrukteur
from ..services.prompts import inpaint_prompt
from .abhaengigkeiten import bild_ki, konstrukteur
from .schemas import EntwuerfeAnfrage, EntwuerfeAntwort

router = APIRouter(prefix="/api", tags=["Entwürfe"])


@router.post("/entwuerfe", response_model=EntwuerfeAntwort)
async def entwuerfe(
    anfrage: EntwuerfeAnfrage,
    ki: BildKI = Depends(bild_ki),
    k: Konstrukteur = Depends(konstrukteur),
    e: Einstellungen = Depends(einstellungen),
) -> EntwuerfeAntwort:
    if not ki.demo and not (anfrage.foto and anfrage.maske):
        raise HTTPException(400, "Foto und Maske fehlen.")
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
        raise HTTPException(502, f"Die Entwürfe konnten nicht erzeugt werden: {err}") from err
    return EntwuerfeAntwort(demo=ki.demo, prompt=prompt, bilder=bilder)
