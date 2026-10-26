# Parawerk

Vom Foto deiner Wohnung zum Bauplan für den Baumarkt.

1. **Foto** hochladen. Optional eine Strecke mit dem Zollstock messen und im Foto antippen: Daraus berechnet Parawerk Breite, Tiefe und Höhe des Bereichs.
2. **Bereich** markieren (auch wo schon etwas steht) und seine Maße eintragen.
3. **Wunsch** eingeben, z. B. „Daybed aus Latten mit Polstern“.
4. **Entwürfe**: Die Bild-KI malt nur in den markierten Bereich. Zurück ins Foto kommt genau dieser Ausschnitt.
5. **Bauplan**: Claude liest aus dem gewählten Entwurf die Konstruktion. Die Engine macht daraus ein baubares, stabiles Möbel aus Baumarkt-Holz. Dazu gehören Einkaufsliste, Zuschnittplan, Montage, 3D-Ansicht und DXF. Per Text anpassbar.

Die Maße richten sich nach deinem Bereich. Ziel ist **baubar und stabil**, nicht pixelgenau wie das Bild.

## Starten

Braucht Python 3.11 oder neuer. Das `python3` aus den Apple Command Line Tools ist 3.9 und zu alt, auf dem Mac also z. B. `brew install python@3.12`.

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env          # Schlüssel eintragen (optional)
uvicorn app.main:app --reload # http://localhost:8000
pytest
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
  main.py                  App-Factory, Router, Sprach-Middleware, Fehlerformat {"fehler": "..."}
  i18n/                    Deutsch und Englisch: t("schlüssel"), Texte für Engine (de/en.py) und Oberfläche (de_ui/en_ui.py)
  config.py                Einstellungen aus Umgebung bzw. .env
  models/                  ── Model: Domäne, ohne Web und ohne KI
    bauteilgraph.py        Schema der Möbelbeschreibung, Bereinigen von KI-Antworten
    verbrauch.py, speicher.py  Datenbank: Verbrauch, Bilder, Aufträge
    gltf.py                3D-Modell als glb
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
    bildarbeit.py          Entwurf ins Foto einsetzen, Ausschnitt fürs Lesen (Pillow)
    auftraege.py           lange KI-Aufrufe im Hintergrund
    kostendeckel.py        Gratis-Kontingent, IP-Limit, Tagesbudget
  controllers/             ── Controller: FastAPI-Router
    seiten.py              GET /
    api_v1.py              /api/v1/… für Website und App (siehe unten)
    schemas.py             Anfragen/Antworten (Pydantic)
    abhaengigkeiten.py     welcher Dienst (echt oder Demo)
  views/                   ── View
    praesentation.py       Ergebnis für die Anzeige aufbereiten
    templates/             Jinja: Seite, Bauplan-Ausschnitt
    static/                CSS, JS (Foto, Maske, Anzeige, 3D), three.js, Demo-Bilder
tests/                     Engine (Referenzfälle), Bauteilgraph, API
mobile/                    Flutter-App (iPhone, Android), spricht /api/v1; siehe mobile/README.md
```

**Sprachen:** Deutsch und Englisch. Die Sprache kommt aus `?sprache=de|en` (Umschalter oben rechts, wird als Cookie gemerkt), sonst aus dem Cookie, dem Header `X-Sprache` oder der Browsersprache. Alles läuft über `app/i18n`: Oberfläche, Fehlermeldungen, Rechenweg, Prüfung, Einkaufsliste und Montage. Claude schreibt die Bauteilnamen in der gewählten Sprache. Intern bleiben die Schlüssel deutsch (Sortiment, Rollen), übersetzt wird erst bei der Anzeige. Neue Texte kommen in beide Kataloge; `tests/test_i18n.py` prüft, dass keiner fehlt.

Website und App sprechen dieselbe API (`/api/v1`). Im Browser passiert nur, was Foto und Maske brauchen: Maske malen, Messstrecke antippen, 3D drehen. Bildarbeit, Rechnen und Bauplan macht der Server.

## Ablauf und Schnittstellen

```
Website / App                          Server (/api/v1)
Foto + Maske + Wunsch  ── entwuerfe ──▶ Bild-KI malt in die Maske, Server setzt nur den Bereich ins Foto
  4 Entwürfe (URLs) ◀── Auftrag fertig
Entwurf + Maske        ── bauplan/lesen ──▶ Server schneidet den Ausschnitt, Claude liest den Bauteilgraph
Graph + Bereich        ── bauplan/berechnen ──▶ Engine: skalieren → einrasten → setzen
                                                 → prüfen/reparieren → Endkontrolle → Bauplan
  Bauplan (JSON, für die Website auch HTML) + 3D-Modell ◀──
Wunsch in Worten       ── bauplan/anpassen ──▶ Claude ändert den Graph, dann neu berechnen
```

## Engine-Tests

Die Engine war zuerst in JavaScript geschrieben. Die Python-Version war bis Commit e27f2f2 in 624 Vergleichsfällen identisch mit ihr: die 4 Demo-Möbel, 10 Blindtests (Ana-White-Pläne) in US- und DE-Sortiment und 600 zufällig variierte Fälle. Teile, Maße, Reparaturen, Prüftexte, Einkauf und Zuschnitt stimmten überein.

Danach wurde die Engine nach dem ersten echten Claude-Durchlauf gezielt verbessert:
- Sitzhöhe auch über Latten messen, wenn Claude sie nicht „sitzflaeche“ nennt.
- Nachführen der Sitzhöhe nur bei unter 25 % Abweichung.
- Breite und Tiefe auf den Bereich zurückrechnen.
- Eine Stütze je Teil statt je Gruppe.
- Einen Nachführschritt nur übernehmen, wenn danach nicht mehr Prüfpunkte offen sind.

In den 624 Fällen ergab das 79 Fälle mit weniger offenen Prüfpunkten, 47 passen jetzt in den Bereich, 1 Fall wurde schlechter. `tests/referenz/engine_faelle.json.gz` (84 Fälle) hält diesen Stand fest. `lounge_ecksofa_claude.json` ist die echte Claude-Lesung, an der die Fehler auffielen.

## Tests und Deploy (GitHub Actions)

`.github/workflows/ci.yml`: Bei jedem Push und Pull Request laufen die Tests. Nach einem Push auf `main` wird bei grünen Tests automatisch auf fly.io deployt.

Einmalig einrichten:
```bash
fly tokens create deploy -x 999999h            # Deploy-Token nur für diese App
gh secret set FLY_API_TOKEN                    # Token einfügen (oder GitHub → Settings → Secrets → Actions)
```

## Veröffentlichen auf fly.io

`Dockerfile` und `fly.toml` (Frankfurt, schläft bei Nichtnutzung, Health-Check `/gesund`) liegen bei.

- Im Browser: fly.io → „Launch an App“ → dieses GitHub-Repository wählen. Unter „Secrets“ `REPLICATE_API_TOKEN` und `ANTHROPIC_API_KEY` eintragen.
- Im Terminal:
  ```bash
  fly launch --copy-config --no-deploy   # App-Namen bei Bedarf ändern
  fly secrets set REPLICATE_API_TOKEN=... ANTHROPIC_API_KEY=...
  fly volumes create parawerk_daten --size 1 --region fra   # Verbrauchs-Datenbank
  fly scale count 1                                         # ein Volume gehört zu genau einer Maschine
  fly deploy
  ```

## API (v1, für Website und Flutter-App)

Unter `/api/v1` gibt es alles als JSON; Bildarbeit (Entwurf einsetzen, Ausschnitt fürs Lesen) und das 3D-Modell (glb) macht der Server. Beschreibung mit allen Feldern: `/docs` bzw. `/openapi.json`.

| Schritt | Aufruf | Antwort |
|---|---|---|
| Foto hochladen | `POST /api/v1/fotos` `{foto}` | Auftrag (Tiefe schätzen), `foto_id`; Ergebnis `tiefe_id`, `flach` |
| Maße messen | `POST /api/v1/masse` `{tiefe_id, maske, messungen: [{a, b, mm}]}` | sofort: `bereich`, `nachmessen`, `hinweise` |
| Entwürfe | `POST /api/v1/entwuerfe` `{foto oder foto_id, maske, wunsch}` | Auftrag, `foto_id`, `maske_id` |
| Nachjustieren | `POST /api/v1/entwuerfe/nachjustieren` `{foto_id, maske_id, entwurf_id, anpassung}` | Auftrag |
| Konstruktion lesen | `POST /api/v1/bauplan/lesen` `{entwurf_id, maske_id, bereich}` | Auftrag |
| Bauplan | `POST /api/v1/bauplan/berechnen` `{graph, bereich}` | sofort: Bauplan, `modell_glb` |
| Anpassen | `POST /api/v1/bauplan/anpassen` `{graph, wunsch}` | Auftrag |
| Stand | `GET /api/v1/auftraege/{id}` | `laeuft` → `fertig` (+ `ergebnis`) oder `fehler` |
| Bilder, 3D | `GET /api/v1/bilder/{id}` | JPEG, PNG oder glb |

Foto und Maske kommen als data-URL; die Maske ist ein PNG, weiß (oder bei transparentem PNG: deckend gemalt) = hier soll das Möbel hin. Header: `X-Geraet` (Geräte-ID, 8–64 Zeichen, von der App einmal erzeugt), `X-Sprache` (`de`/`en`). Im Browser ersetzt das Cookie `geraet` den Header. Bilder und Aufträge werden nach 7 Tagen gelöscht. `berechnen?mit_html=true` liefert zusätzlich den fertigen Bauplan-Ausschnitt für die Website.

## Maße aus dem Foto

Beim Hochladen schätzt Apples Depth Pro (auf Replicate, ca. 0,2–0,4 Cent je Foto, wenige Sekunden) für jeden Bildpunkt die Entfernung. Den genauen Maßstab liefert eine Messung des Nutzers: zwei Punkte im Foto und ihre echte Länge. Damit wird die Tiefenkarte skaliert (`app/models/raum.py`):
- Der Boden wird als Ebene gesucht (gibt „oben“ und die Bodenhöhe).
- Reicht die Markierung bis auf den Boden, ist ihre Unterkante die Vorderkante des Möbels: daraus Breite und Abstand zur Wand dahinter (Tiefe); die Oberkante wird auf die Vorder- bzw. Rückseite projiziert (Höhe).
- Sonst (Wandregal) gelten Breite und Höhe auf der Wand.
- Zwei Messungen werden verglichen; weichen sie mehr als 8 % ab, heißt es „nachmessen“.

Ohne Replicate-Schlüssel, bei Fehlern oder über dem Limit (`FOTOS_PRO_TAG`, Standard 20) wird „flach“ gemessen, wie mit einem Lineal auf dem Foto. Getestet an einem gerechneten Zimmer mit bekannten Maßen (`tests/test_raum.py`), auch mit verrauschter Tiefe.

## Selbstkontrolle beim Lesen

Nach dem Lesen rechnet der Server das Modell einmal durch und zeichnet es (`models/ansicht.py`, Schrägansicht von vorne links oben). Claude bekommt Entwurf und Modellbild nebeneinander, prüft wie ein Schreiner (Form, Lehne, Lattenrichtung, Proportionen, schwebende oder fehlende Teile) und liefert bei Mängeln einen korrigierten Bauteilgraph (`pruef_prompt`). Meldet die Endkontrolle der Engine danach noch Fehler (z. B. Teile ohne Verbindung), gibt es eine zweite Runde, in der Claude diese Meldungen mitbekommt (`KONTROLLRUNDEN`, Standard 2). Je Runde ca. 5 Cent; scheitert die Kontrolle, bleibt der letzte gute Stand. Die Korrekturen stehen im Ergebnis des Auftrags unter `pruefung` und erscheinen auf Website und in der App. Abschalten mit `SELBSTKONTROLLE=false`.

## Kostendeckel

Jeder bezahlte KI-Aufruf wird vorher in der Tabelle `verbrauch` eingetragen (`services/kostendeckel.py`), schlägt er fehl, wird er wieder gestrichen. Im Demo-Modus zählt nichts.

| Regel | Standard | Einstellung |
|---|---|---|
| Gratis-Runden je Gerät (1 Runde = 4 Entwürfe ≈ 0,21 $) | 1 | `GRATIS_RUNDEN` |
| Gratis-Nachjustieren je Gerät (≈ 0,045 $) | 2 | `GRATIS_NACHJUSTIEREN` |
| Runden je IP und Tag (gegen gelöschte Cookies) | 3 | `IP_RUNDEN_PRO_TAG` |
| Lesungen / Anpassungen je Gerät und Tag | 5 / 10 | `LESEN_PRO_TAG`, `ANPASSEN_PRO_TAG` |
| Fotos mit Tiefe je Gerät und Tag (≈ 0,004 $; darüber wird flach gemessen) | 20 | `FOTOS_PRO_TAG` |
| Tagesbudget für alle zusammen, gilt auch für Admin | 5 $ | `TAGESBUDGET_USD` |

**Testcodes:** `TESTCODES="KUMPEL:10,FREUNDE:5:3"` (Code:Runden[:Geräte], ohne Geräte-Angabe genau eins). Eingelöst wird auf der Website unter „Testcode eingeben“ bzw. in der App (`POST /api/v1/code`). Ein Code gibt die Runden zusätzlich (und doppelt so viele Änderungen), für Geräte mit Code gilt das IP-Limit nicht; das Tagesbudget bleibt. Entfernt man einen Code aus `TESTCODES`, fällt sein Bonus weg.

Die Geräte-ID ist ein Cookie, das die Startseite vergibt. Mit `ADMIN_SCHLUESSEL` gesetzt hebt `/?schluessel=…` die Kontingente für diesen Browser auf (nicht das Tagesbudget). `GET /api/v1/kontingent` zeigt, was das Gerät noch gratis hat.

Datenbank: ohne `DATABASE_URL` eine SQLite-Datei im Temp-Ordner. Auf fly.io eine SQLite-Datei auf dem Volume `/data` (siehe `fly.toml`). Für Postgres genügt `DATABASE_URL=postgres://…`; Tabellen legt die App selbst an.

## Bild-KI austauschen (z. B. Midjourney)

Eine Bild-KI ist jede Klasse mit `entwerfen(foto, maske, prompt, seeds)` (siehe `services/bild_ki.py`). Eingesetzt wird sie in `controllers/abhaengigkeiten.py`. Midjourney hat derzeit keine offizielle API. Drittanbieter steuern dafür Konten automatisiert, was gegen die Nutzungsbedingungen verstößt. Außerdem bearbeiten sie mit Maske nur Bilder, die Midjourney selbst erzeugt hat. Sobald es eine offizielle API mit Maske gibt, genügt eine neue Klasse.

## Grenzen

- Statik nach Faustregeln (Spannweite aus Holzstärke), keine Ingenieursberechnung.
- Nur achsparallele Teile, keine Schrägen und Rundungen.
- Sortiment nach deutschen Baumarkt-Angeboten (OBI, toom, Hornbach, Okt. 2026); im eigenen Markt prüfen.
- Ohne Messung kommen die Maße aus deiner Eingabe. Gemessen wird ein Vorschlag (meist auf wenige Prozent genau), der Bereich gilt als Umriss des Möbels: Unterkante = Vorderkante am Boden.

## Verbesserungsideen

### Interner Prüf-Loop zwischen Claude und Bild-KI

Die Bild-KI malt manchmal Möbel, die man so nicht bauen kann: Rundungen, schwebende Teile, Verbindungen ohne Auflager, zu dünne Hölzer, falsche Proportionen. Bisher fängt das erst die Engine ab. Sie repariert die Konstruktion, das Bild bleibt aber, wie es war. Besser wäre ein Loop vor dem Anzeigen:

1. Die Bild-KI malt einen Entwurf in die Maske.
2. Claude prüft den Ausschnitt auf Baubarkeit und nennt konkret, was unrealistisch ist, z. B. „Armlehne gebogen“, „Sitzfläche ohne Beine in der Mitte“ oder „Latten dünner als 2 cm“.
3. Zusätzlich liest Claude den Bauteilgraph, und die Engine rechnet ihn durch. Jede Reparatur ist ein Hinweis, dass das Bild nicht stimmt, z. B. „Fußriegel ergänzt“, „Mittelsteg eingefügt“ oder „Latte zu lang, gestoßen“.
4. Claude formuliert daraus einen Korrektur-Prompt: was bleiben soll (Stil, Farbe, Gesamtform) und was sich ändern muss.
5. Die Bild-KI malt den Entwurf neu, mit gleichem Seed und gleicher Maske. Dadurch ändert sich nur das Nötige.
6. Der Loop wiederholt sich, bis Claude nichts mehr findet und die Engine keine Reparatur mehr braucht, höchstens 2–3 Runden.

Ergebnis: Die angezeigten Entwürfe sind schon baubar, und Bild und Bauplan passen zusammen. Kosten: je Runde ein Inpainting-Aufruf und ein bis zwei Claude-Aufrufe pro Entwurf. Den Loop eventuell nur für den gewählten Entwurf laufen lassen.

Umsetzung: ein neuer Dienst `services/pruefer.py` (Claude: Bild → Mängelliste und Korrektur-Prompt). Dazu eine Funktion, die Bild-KI, Prüfer und Engine im Wechsel aufruft, angebunden an `controllers/api_v1.py` (Auftrag `entwuerfe`). Den Fortschritt je Runde an die Oberfläche melden, z. B. „Runde 2: Armlehne begradigt“.
