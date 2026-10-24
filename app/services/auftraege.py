"""Aufträge: lange KI-Aufrufe laufen im Hintergrund, die App fragt den Stand ab.

So hängt das Handy nicht eine Minute an einer Verbindung, die beim App-Wechsel abreißen kann. Status und
Ergebnis stehen in der Datenbank (``models/speicher.py``). Die Sprache der Anfrage gilt auch im Auftrag,
weil ``asyncio.create_task`` den Kontext mitnimmt.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import Engine

from ..i18n import t
from ..models import speicher
from ..models.bauteilgraph import GraphFehler
from .fehler import DienstFehler

log = logging.getLogger("parawerk.auftraege")
_laufend: set[asyncio.Task] = set()  # Referenzen halten, sonst räumt Python laufende Tasks ab


async def starten(db: Engine, geraet: str, art: str, arbeit: Callable[[], Awaitable[dict]],
                  fehlertext: str, bei_fehler: Callable[[], Awaitable[None]] | None = None) -> str:
    """Legt den Auftrag an und startet ``arbeit`` im Hintergrund. ``fehlertext`` ist ein i18n-Schlüssel mit {err}."""
    aid = await run_in_threadpool(speicher.auftrag_anlegen, db, geraet, art)

    async def lauf() -> None:
        try:
            ergebnis = await arbeit()
        except (DienstFehler, GraphFehler) as err:
            if bei_fehler:
                await bei_fehler()
            await run_in_threadpool(speicher.auftrag_beenden, db, aid, None, t(fehlertext, err=err))
        except Exception:  # unerwartet: nicht abstürzen, sondern lesbar melden
            log.exception("Auftrag %s (%s) fehlgeschlagen", aid, art)
            if bei_fehler:
                await bei_fehler()
            await run_in_threadpool(speicher.auftrag_beenden, db, aid, None, t(fehlertext, err=t("fehler.intern")))
        else:
            await run_in_threadpool(speicher.auftrag_beenden, db, aid, ergebnis)

    task = asyncio.create_task(lauf())
    _laufend.add(task)
    task.add_done_callback(_laufend.discard)
    return aid


async def alle_fertig() -> None:
    """Für Tests: warten, bis keine Aufträge mehr laufen."""
    while _laufend:
        await asyncio.gather(*list(_laufend), return_exceptions=True)
