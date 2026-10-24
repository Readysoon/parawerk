# Hinweise für Claude

## So schreibst du mir
- Einfach und kurz: kurze Sätze, wenig Fachwörter, Fachbegriffe kurz erklären.
- Erst das Ergebnis, dann was ich tun muss.
- Befehle als nummerierte Schritte, jeder Befehl in einem eigenen Codeblock.

## Projekt
Parawerk: Foto der Wohnung → Bereich markieren → Bild-KI malt Entwürfe → Claude liest die Konstruktion → Engine macht daraus einen baubaren Bauplan. Aufbau und Befehle stehen in `README.md`.
- Tests: `python3.12 -m pytest -q` (müssen vor jedem Commit grün sein)
- Texte immer zweisprachig in `app/i18n/` (de + en)
- Deploy läuft automatisch über GitHub Actions nach `git push`
