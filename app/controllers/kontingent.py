"""Kontingent-Controller: was dieses Gerät noch gratis hat, und die Hilfen für die anderen Controller."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.concurrency import run_in_threadpool

from ..config import Einstellungen, einstellungen
from ..services.kostendeckel import Gesperrt, Kostendeckel, Kunde
from .abhaengigkeiten import kostendeckel, kunde

router = APIRouter(prefix="/api", tags=["Kontingent"])


@router.get("/kontingent")
async def kontingent(k: Kunde = Depends(kunde), deckel: Kostendeckel = Depends(kostendeckel),
                     e: Einstellungen = Depends(einstellungen)) -> dict:
    """Verbleibende Gratis-Runden und -Änderungen (``null`` = unbegrenzt bzw. Demo-Modus)."""
    if not e.bild_ki_aktiv:
        return {"runden": None, "nachjustieren": None}
    return await run_in_threadpool(deckel.stand, k)


async def reservieren(deckel: Kostendeckel, art: str, k: Kunde) -> int:
    """Kosten vor dem Aufruf eintragen; ist das Kontingent oder Budget erschöpft, gibt es eine lesbare Fehlermeldung."""
    try:
        return await run_in_threadpool(deckel.reservieren, art, k)
    except Gesperrt as g:
        raise HTTPException(g.status, str(g)) from g


async def erstatten(deckel: Kostendeckel, eintrag: int | None) -> None:
    await run_in_threadpool(deckel.erstatten, eintrag)
