"""Nachjustieren mit mehreren Bild-KIs vergleichen (läuft lokal, braucht REPLICATE_API_TOKEN und ANTHROPIC_API_KEY in .env).

    python -m scripts.anpassen_vergleich "niedriger"
    python -m scripts.anpassen_vergleich "eine Schublade in der Sitzbank" --nr 2

Nimmt die letzte Entwurfsrunde aus der lokalen Datenbank (parawerk.db), Entwurf Nr. --nr (1–4), schneidet wie die
App den Bereich um die Markierung aus, lässt Claude einmal die Anweisung schreiben und schickt sie an jedes Modell.
Ergebnis in vergleich/: je Modell ein Bild und vergleich.jpg nebeneinander (links das Original).
Kosten grob 0,04–0,15 $ je Modell, dazu ein Claude-Aufruf.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import time
from pathlib import Path

from PIL import Image, ImageDraw
from sqlalchemy import select

from app.config import Einstellungen
from app.models import speicher
from app.models.verbrauch import datenbank
from app.services import bildarbeit as ba
from app.services.bild_ki import ReplicateFluxFill
from app.services.konstrukteur import ClaudeKonstrukteur

MODELLE = [
    "black-forest-labs/flux-kontext-pro",  # jetzt im Einsatz, ca. 0,04 $
    "black-forest-labs/flux-kontext-max",  # ca. 0,08 $
    "black-forest-labs/flux-2-pro",
    "google/nano-banana-pro",
    "bytedance/seedream-4",
    "qwen/qwen-image-edit",
]


def letzte_runde(db) -> dict:
    with db.connect() as c:
        z = c.execute(select(speicher.auftraege.c.ergebnis).where(speicher.auftraege.c.art == "entwuerfe",
                                                                  speicher.auftraege.c.status == "fertig")
                      .order_by(speicher.auftraege.c.erstellt.desc())).first()
    if not z:
        raise SystemExit("Keine Entwurfsrunde in der lokalen Datenbank (älter als 7 Tage wird gelöscht).")
    return json.loads(z.ergebnis)


async def main(anpassung: str, nr: int, modelle: list[str]) -> None:
    e = Einstellungen()
    if not (e.replicate_api_token and e.anthropic_api_key):
        raise SystemExit("REPLICATE_API_TOKEN und ANTHROPIC_API_KEY in .env nötig.")
    db = datenbank(e.database_url)
    runde = letzte_runde(db)
    if "foto_id" not in runde:
        raise SystemExit("Die letzte Entwurfsrunde ist von vor dem Update. Bitte in der App einmal neu entwerfen.")
    laden = lambda bid: ba.aus_bytes(speicher.bild_laden(db, bid)[0])  # noqa: E731
    foto, maske = laden(runde["foto_id"]), laden(runde["maske_id"]).convert("L")
    entwurf = laden(runde["entwuerfe"][nr - 1]["id"])
    box = ba.bearbeitungs_rahmen(maske, entwurf.size)
    teil = ba.vergroessern(entwurf.convert("RGB").crop(box))
    teil_url = ba.als_data_url(ba.jpeg(teil, 92), "image/jpeg")

    kon = ClaudeKonstrukteur(e.anthropic_api_key, e.anthropic_model)
    prompt = await kon.bearbeitungs_prompt("", anpassung, teil_url)
    print("Anweisung:", prompt, "\n")

    aus = Path("vergleich")
    aus.mkdir(exist_ok=True)
    bilder = [("original", teil)]
    for m in modelle:
        ki = ReplicateFluxFill(e.replicate_api_token, e.replicate_model, m)
        start = time.monotonic()
        try:
            neu = ba.aus_data_url(await ki.bearbeiten(teil_url, prompt, secrets.randbelow(10**9)))
        except Exception as err:  # noqa: BLE001  (ein Modell darf scheitern, die anderen laufen weiter)
            print(f"{m}: FEHLER {str(err)[:200]}")
            continue
        sek = time.monotonic() - start
        pruefung = await kon.aenderung_pruefen(anpassung, teil_url, ba.als_data_url(ba.jpeg(neu, 90), "image/jpeg"))
        print(f"{m}: {sek:.0f} s, Claude: {'umgesetzt' if pruefung['umgesetzt'] else 'NICHT umgesetzt'} – {pruefung['grund']}")
        ganz = ba.einsetzen(foto, maske, ba.zurueckkleben(entwurf, neu, box))
        datei = aus / (m.replace("/", "_") + ".jpg")
        datei.write_bytes(ba.jpeg(ganz, 90))
        bilder.append((m.split("/")[-1], neu.resize(teil.size)))

    h = 420
    reihe = [(n, b.resize((round(b.width * h / b.height), h))) for n, b in bilder]
    blatt = Image.new("RGB", (sum(b.width for _, b in reihe) + 10 * len(reihe), h + 30), "white")
    x = 0
    for n, b in reihe:
        blatt.paste(b, (x, 30))
        ImageDraw.Draw(blatt).text((x + 4, 8), n, fill="black")
        x += b.width + 10
    blatt.save(aus / "vergleich.jpg", quality=88)
    print(f"\nFertig: {aus / 'vergleich.jpg'}")


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("anpassung")
    a.add_argument("--nr", type=int, default=1, help="Entwurf 1–4 der letzten Runde")
    a.add_argument("--modelle", nargs="*", default=MODELLE)
    args = a.parse_args()
    asyncio.run(main(args.anpassung, args.nr, args.modelle))
