# Nischenwerk

Vom Foto deiner Wohnung zum Bauplan für den Baumarkt.

1. **Foto** hochladen, optional mit einem A4-Blatt an der Wand für echte Maße.
2. **Bereich** markieren (auch wo schon etwas steht) und seine Maße eintragen.
3. **Wunsch** eingeben, z. B. „Daybed aus Latten mit Polstern“.
4. **Entwürfe**: Die Bild-KI malt nur in den markierten Bereich. Zurück ins Foto kommt genau dieser Ausschnitt.
5. **Bauplan**: Claude liest aus dem gewählten Entwurf die Konstruktion. Die Engine macht daraus ein baubares, stabiles Möbel aus Baumarkt-Holz. Dazu gehören Einkaufsliste, Zuschnittplan, Montage, 3D-Ansicht und DXF. Per Text anpassbar.

Die Maße richten sich nach deinem Bereich. Ziel ist **baubar und stabil**, nicht pixelgenau wie das Bild.

## Starten

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # Schlüssel eintragen (optional)
uvicorn app.main:app --reload # http://localhost:8000
pytest                        # 102 Tests
```

| Variable | Wofür |
|---|---|
| `REPLICATE_API_TOKEN` | Entwürfe per Inpainting (FLUX Fill Pro), replicate.com → API tokens |
| `ANTHROPIC_API_KEY` | Konstruktion aus dem Entwurf lesen und per Text anpassen, console.anthropic.com |
| `ANTHROPIC_MODEL` | optional, Standard `claude-sonnet-5-5` |
| `REPLICATE_MODEL` | optional, Standard `black-forest-labs/flux-fill-pro` |
| `SORTIMENT` | `DE` (Baumarkt, Standard) oder `US` (Bauholz) |

**Ohne Schlüssel** läuft der Demo-Modus mit Beispielzimmer, vier fertigen Entwürfen und den dazu gelesenen Konstruktionen. Die Engine rechnet dabei echt. Nur das Anpassen per Text braucht den Claude-Schlüssel.

API-Dokumentation: `/docs`.

## Aufbau (MVC)

```
app/
  main.py                  App-Factory, Router, Fehlerformat {"fehler": "..."}
  config.py                Einstellungen aus Umgebung bzw. .env
  models/                  ── Model: Domäne, ohne Web und ohne KI
    bauteilgraph.py        Schema der Möbelbeschreibung, Bereinigen von KI-Antworten
    sortiment.py           Holz im Baumarkt (DE/US), Handelslängen, Schnittpreis
    dxf.py                 Zuschnitte als DXF
    engine/                Bauteil-Engine
      aufbau.py            skalieren (Matratze, Sitzhöhe) und auf Sortiment einrasten
      setzen.py            Überschneidungen lösen, Fugen schließen, Enden anschließen
      reparatur.py         Handelslänge, Spannweiten, Auflager, Wackeln → Teile ergänzen
      pruefung.py          Endkontrolle
      bauplan.py           Einkauf, Zuschnitt (Stangen und Platten), Schrauben, Montage
  services/                ── Model: Anbindung externer KI, je mit Demo-Ersatz
    bild_ki.py             Inpainting (Replicate), austauschbar
    konstrukteur.py        Bild → Bauteilgraph, Graph + Wunsch → Graph (Claude)
    prompts.py             Anweisungen an Bild-KI und Claude
  controllers/             ── Controller: FastAPI-Router
    seiten.py              GET /
    entwuerfe.py           POST /api/entwuerfe
    bauplan.py             POST /api/bauplan/{lesen,anpassen,berechnen,dxf}
    schemas.py             Anfragen/Antworten (Pydantic)
    abhaengigkeiten.py     welcher Dienst (echt oder Demo)
  views/                   ── View
    praesentation.py       Ergebnis für die Anzeige aufbereiten
    templates/             Jinja: Seite, Bauplan-Ausschnitt
    static/                CSS, JS (Foto, Maske, Zusammensetzen, 3D), three.js, Demo-Bilder
tests/                     Engine (Referenzfälle), Bauteilgraph, API
```

Im Browser passiert nur, was Foto und Maske brauchen: Maske malen, A4-Maßstab, Entwurf zurück ins Foto setzen, 3D drehen. Gerechnet und gerendert wird auf dem Server.

## Ablauf und Schnittstellen

```
Browser                                Server
Foto + Maske + Wunsch  ── /api/entwuerfe ──▶ Bild-KI malt in die Maske
  setzt nur den Maskenbereich ins Foto ◀── Bilder
Ausschnitt des Entwurfs ── /api/bauplan/lesen ──▶ Claude liest Bauteilgraph
Graph + Bereich         ── /api/bauplan/berechnen ──▶ Engine: skalieren → einrasten → setzen
                                                       → prüfen/reparieren → Endkontrolle → Bauplan
  Bauplan (HTML) + 3D-Modell ◀──
Wunsch in Worten        ── /api/bauplan/anpassen ──▶ Claude ändert den Graph, dann neu berechnen
```

## Engine-Tests

Die Engine war zuerst in JavaScript geschrieben. `tests/referenz/js_engine_faelle.json.gz` enthält 84 Fälle mit dem Ergebnis der JS-Engine: die 4 Demo-Möbel, 10 Blindtests (Ana-White-Pläne) im US- und im DE-Sortiment und 60 zufällig variierte Fälle. Die Python-Engine liefert in allen Fällen dasselbe Ergebnis: Teile, Maße, Reparaturen, Prüftexte, Einkauf und Zuschnitt. Vor dem Umzug wurde das an 624 Fällen geprüft.

## Veröffentlichen auf fly.io

`Dockerfile` und `fly.toml` (Frankfurt, schläft bei Nichtnutzung, Health-Check `/gesund`) liegen bei.

- Im Browser: fly.io → „Launch an App“ → dieses GitHub-Repository wählen. Unter „Secrets“ `REPLICATE_API_TOKEN` und `ANTHROPIC_API_KEY` eintragen.
- Im Terminal:
  ```bash
  fly launch --copy-config --no-deploy   # App-Namen bei Bedarf ändern
  fly secrets set REPLICATE_API_TOKEN=... ANTHROPIC_API_KEY=...
  fly deploy
  ```

## Bild-KI austauschen (z. B. Midjourney)

Eine Bild-KI ist jede Klasse mit `entwerfen(foto, maske, prompt, seeds)` (siehe `services/bild_ki.py`). Eingesetzt wird sie in `controllers/abhaengigkeiten.py`. Midjourney hat derzeit keine offizielle API. Drittanbieter steuern dafür Konten automatisiert, was gegen die Nutzungsbedingungen verstößt. Außerdem bearbeiten sie mit Maske nur Bilder, die Midjourney selbst erzeugt hat. Sobald es eine offizielle API mit Maske gibt, genügt eine neue Klasse.

## Grenzen

- Statik nach Faustregeln (Spannweite aus Holzstärke), keine Ingenieursberechnung.
- Nur achsparallele Teile, keine Schrägen und Rundungen.
- Sortiment nach deutschen Baumarkt-Angeboten (OBI, toom, Hornbach, Okt. 2026); im eigenen Markt prüfen.
- Ohne A4-Blatt kommen die Maße aus deiner Eingabe.
