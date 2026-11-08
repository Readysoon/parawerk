# Parawerk · Aufgaben- und Qualitätsplan

**Trello-Vorlage für Lennart und Philipp · 17 Karten · Planungsvorschlag vom 8. November 2026**

> **Fokus:** bessere Entwurfsbilder, größere Übereinstimmung von Bild und 3D sowie konsistente, konstruktiv geprüfte Baupläne.
> Die Karten beschreiben geplante Arbeit. Ein Trello-Board wurde damit noch nicht angelegt.

## Navigation

- [1. Hier anfangen](#start)
- [2. Alle Aufgaben auf einen Blick](#aufgaben)
- [3. Zusammenarbeit und Boardregeln](#zusammenarbeit)
- [4. Qualitätsziele](#qualitaetsziele)
- [5. Vollständige Trello-Karten](#karten)
- [6. Vorlage für neue Karten](#kartenvorlage)
- [7. Ausgangspunkt und Quellen](#quellen)

---

<a id="start"></a>

## 1. Hier anfangen

| Reihenfolge | Aufgabe | Verantwortung |
|---|---|---|
| **Parallel starten** | [Q01 · Referenzfälle und Bewertungsmaßstab](#q01) | Philipp |
| **Parallel starten** | [P01 · Fehlerhafte Baupläne vor Export sperren](#p01) | Lennart |
| **Danach** | [Q02 · Ausgangsqualität reproduzierbar messen](#q02) | Lennart |
| **Nächster Schwerpunkt** | [B01 · Anforderungen erfassen](#b01) → [B02 · Bildgenerierung vergleichen](#b02) | Lennart |
| **Parallel vorbereiten** | [D01 · Bild und 3D systematisch vergleichen](#d01) | Philipp |

**Vor zusätzlichen bezahlten Korrekturschleifen:** [O01 · Kosten- und Wiederholungsgrenzen absichern](#o01).

Philipp beginnt Q01 mit fünf Fällen zur gemeinsamen Kalibrierung und vervollständigt danach den Referenzsatz. Q02 startet, sobald Referenzeingaben und Kriterien feststehen.

**Terminstatus:** „Diese Woche“ ist eine vorgeschlagene Startauswahl, keine belastbare Aufwandsschätzung oder Terminzusage.

---

<a id="aufgaben"></a>

## 2. Alle Aufgaben auf einen Blick

### Prioritäten

| Kürzel | Bedeutung |
|---|---|
| **P0** | Voraussetzung für die Freigabe von Bauplänen beziehungsweise des geprüften Pilotmöbels |
| **P1** | Ergebnisqualität, Messbarkeit und verlässliche Abnahme |
| **P2** | Betriebliche Weiterentwicklung; Abhängigkeiten einzelner Tests beachten |

### Aufgaben nach Arbeitsbereich

**Messbarkeit und Referenzen**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [Q01](#q01) | Referenzfälle und Fehlerkatalog definieren | Philipp | P1 |
| [Q02](#q02) | Ausgangsqualität reproduzierbar messen | Lennart | P1 |

**Bildqualität**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [B01](#b01) | Gestaltungswunsch als prüfbare Anforderungen erfassen | Lennart | P1 |
| [B02](#b02) | Bildmodelle und Generierungseinstellungen vergleichen | Lennart | P1 |
| [B03](#b03) | Entwurfsbilder prüfen und gezielt korrigieren | Lennart | P1 |

**3D-Genauigkeit und Abgleich**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [D01](#d01) | 3D-Bildtreue unabhängig bewertbar machen | Philipp | P1 |
| [D02](#d02) | Astra-Rekonstruktion mit Bildabgleich verbessern | Lennart | P1 |
| [C01](#c01) | Abweichungen zwischen Bild, 3D und Konstruktion abgleichen | Lennart | P1 |

**Raumaufnahme und Maße**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [R01](#r01) | Raumaufnahme und Maßermittlung absichern | Lennart | P1 |

**Baupläne und praktische Prüfung**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [P01](#p01) | Fehlerhafte Baupläne vor Export sperren | Lennart | P0 |
| [P02](#p02) | Zuschnitt, Verbindungen und Montage konsistent prüfen | Lennart | P0 |
| [P03](#p03) | Fachliche Prüfung und dokumentierten Testbau organisieren | Philipp | P0 |

**Kosten, Projekte und Wiederherstellung**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [O01](#o01) | Kosten- und Wiederholungsgrenzen atomar absichern | Lennart | P1 |
| [O02](#o02) | Projektversionen und laufende Aufträge wiederherstellen | Lennart | P2 |

**Abnahme und Nutzertests**

| Karte | Aufgabe | Verantwortung | Priorität |
|---|---|---|---|
| [T01](#t01) | Zurückgehaltene Fälle blind abnehmen | Philipp | P1 |
| [T02](#t02) | Den gesamten iOS-Ablauf mit fünf Personen testen | Philipp | P1 |
| [Q03](#q03) | Qualitätsabnahme vor jeder Veröffentlichung verankern | Lennart | P1 |

---

<a id="zusammenarbeit"></a>

## 3. Zusammenarbeit und Boardregeln

### Rollenverteilung

**Vorschlag — gemeinsam an Eure tatsächlichen Kompetenzen anpassen:**

| Person | Schwerpunkt |
|---|---|
| **Lennart** | Technische Umsetzung, Modelle und Prompts, API, Viewer und Konstruktionsengine |
| **Philipp** | Referenzfälle, Anforderungsklarheit, Blindbewertung, Testpersonen und fachliche Prüfer koordinieren |

Jede Karte hat **genau eine ergebnisverantwortliche Person**. Die Gegenprüfung übernimmt jeweils der andere. Wenn Ihr beide technisch arbeitet, könnt Ihr die Zuständigkeiten nach Verfügbarkeit ändern.

Bei technischen Änderungen prüft Philipp zunächst die Ergebnisse. Das ersetzt keinen fachkundigen Code- oder Konstruktionsreview. Tragfähigkeit und praktische Bauausführung benötigen zusätzlich eine dafür qualifizierte Person.

### Trello-Listen

**Priorisiert → Diese Woche → In Arbeit → Gegenprüfung → Erledigt**

| Liste | Bedeutung |
|---|---|
| **Priorisiert** | Aufgabe beschrieben; Abhängigkeiten erkennbar |
| **Diese Woche** | Kleine gemeinsame Startauswahl |
| **In Arbeit** | Höchstens eine Karte je Person gleichzeitig |
| **Gegenprüfung** | Ergebnis und Nachweise liegen vollständig vor |
| **Erledigt** | Abnahmekriterien erfüllt und Gegenprüfung dokumentiert |

**Blockaden:** Label „Blockiert“ und konkrete Abhängigkeit ergänzen. Große Karten in eigenständig abnehmbare Ergebnisse zerlegen. Abo-, Store- und Marketingpakete bleiben hinter den aktuellen Qualitätsblockaden zurückgestellt.

### Arbeitsrhythmus

| Zeitpunkt | Format | Ergebnis |
|---|---|---|
| **Wochenstart** | 20 Minuten gemeinsam | Ein Ergebnisziel und wenige Karten für „Diese Woche“ |
| **Während der Arbeit** | Kurzes Update auf der Karte | Erreichtes Ergebnis · Blockade · nächster Schritt |
| **Wochenabschluss** | 30 Minuten gemeinsame Demo | Dieselben Fälle vergleichen; Verbesserungen und Regressionen getrennt bewerten |

**Fehlerberichte enthalten:** Fall-ID, Eingabe, tatsächliches Ergebnis und erwartetes Ergebnis.

---

<a id="qualitaetsziele"></a>

## 4. Qualitätsziele

> **Alle numerischen Grenzwerte sind Vorschläge.** Sie sind bislang weder als Ausgangsqualität gemessen noch als erreicht nachgewiesen. Erst nach der Ausgangsmessung gemeinsam verbindlich festlegen.

### Bilder

| Prüfen | Vorgeschlagenes Ziel | Bewertungsgrundlage |
|---|---|---|
| **Wunschtreue** | Mindestens 90 % der einzelnen Entwürfe ohne schweren Verstoß gegen Muss-Anforderungen | Alle Varianten und Wiederholungen zählen. |
| **Raumerhalt** | Keine unzulässige Änderung außerhalb der freigegebenen Bearbeitungszone | Maske und zulässigen Übergangsrand vorher definieren. |

### 3D und Übereinstimmung

| Prüfen | Vorgeschlagenes Ziel | Bewertungsgrundlage |
|---|---|---|
| **Visuelle Bildtreue** | Mindestens 80 % der Bild-Modell-Paare erreichen mindestens 4 von 5 Punkten | Silhouette, sichtbare Teile und Proportionen; Bewertungsanker und Kamerapose berücksichtigen. |
| **Geometrische Genauigkeit** | Höchstens 5 % Abweichung der äußeren Abmessungen je Achse | Nur synthetische Testobjekte mit bekannten Sollmaßen; kein Genauigkeitsversprechen für reale Einzelfotos. |
| **Durchgängigkeit** | Wesentliche Abweichungen vor Bauplanfreigabe sichtbar und bestätigt | Bild, Vorschau, Konstruktionsmodell und Plan desselben Falls vergleichen. |

### Baupläne

| Prüfen | Freigabekriterium | Grenze der Aussage |
|---|---|---|
| **Konstruktive Konsistenz** | Keine bekannten kritischen Geometrie-, Tragfähigkeits- oder Konsistenzfehler im freigegebenen Plan | Softwaretests und Vorbemessung ersetzen keine praktische oder fachliche Validierung. |

### Was als Fehler zählt

„Halluzination“ wird hier als konkrete Anforderungsverletzung erfasst:

- ungewollte zusätzliche Objekte;
- veränderte Raummerkmale;
- verlorene Muss-Anforderungen;
- als gesichert dargestellte Schätzmaße.

Verdeckte Geometrie bleibt eine **Annahme**. Ihre Richtigkeit lässt sich aus einem einzelnen sichtbaren Ausschnitt nicht nachweisen. Die visuelle Vorschau ist weiterhin eine eigenständige Rekonstruktion.

### Umfang der ersten Prüfung

**20 Referenzfälle = 12 Entwicklungsfälle + 8 zurückgehaltene Abnahmefälle.**

Das ist ein pragmatischer Start, keine statistisch repräsentative Stichprobe. Die tatsächliche Fehlerquote ist derzeit nicht belastbar bekannt. Neue beobachtete Fehler ergänzen den Referenzsatz. Automatische Modellurteile werden durch menschliche Bewertung kontrolliert.

---

<a id="karten"></a>

## 5. Vollständige Trello-Karten

Die Karten sind nach Arbeitsbereichen geordnet. Jede enthält Ziel, Lieferung, Voraussetzungen, Abnahmekriterien und Nachweis. Für das Ergebnisprotokoll gilt die gemeinsame Vorlage in [Abschnitt 6](#kartenvorlage).

### Messbarkeit und Referenzen

<a id="q01"></a>

#### Q01 · Referenzfälle und Fehlerkatalog definieren

**P1** · Verantwortlich: **Philipp** · Gegenprüfung: **Lennart**

**Voraussetzungen:** keine

**Ziel:** Eine gemeinsame, überprüfbare Bedeutung von guten Bildern, genauer 3D-Rekonstruktion und brauchbaren Bauplänen festlegen.

**Lieferung:** 20 dokumentierte Fälle: 12 Entwicklung, 8 zurückgehaltene Abnahme. Aufteilung und Qualitätsziele vor der Optimierung festschreiben.

**Abnahme**

- [ ] Je Fall Raumfoto, Maske, präziser Wunsch und gemessene Bereichsmaße; Nutzung der Bilder geklärt.
- [ ] Muss-Kriterien dokumentiert: Möbeltyp, Anzahl, Position, Material, Farbe und ausdrücklich ausgeschlossene Zusätze.
- [ ] Fehlerarten getrennt: Wunschverstoß, Raumänderung, falsche Proportion, ungesicherte Maßbehauptung, Geometrie- oder Konstruktionsfehler.
- [ ] Bewertungsschema und schwere Fehler gemeinsam an fünf Beispielen kalibriert; acht Abnahmefälle bleiben von der Optimierung ausgeschlossen.
- [ ] Gegenprüfung durch Lennart dokumentiert.

**Nachweis:** Referenzordner + Bewertungsbogen mit Beispielurteilen; keine Qualitätsverbesserung allein aus subjektivem Eindruck ableiten.

---

<a id="q02"></a>

#### Q02 · Ausgangsqualität reproduzierbar messen

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [Q01](#q01)

**Ziel:** Für jede spätere Änderung einen nachvollziehbaren Vorher-/Nachher-Vergleich ermöglichen.

**Lieferung:** Ein Auswertungsdurchlauf mit Bild, 3D-Ansichten, Konstruktionsmodell und Bauplan je Referenzfall.

**Abnahme**

- [ ] Fall-ID, Promptversion, Modellkennung, Einstellungen, Maße, Antwortstatus und tatsächliche oder geschätzte Kosten protokolliert.
- [ ] Bilder, 3D-Szene und Bauplan derselben Auswahl eindeutig zugeordnet.
- [ ] Wiederholungen mit gleicher Eingabe durchgeführt; gleiche Seeds nur verwenden, soweit der Anbieter sie unterstützt, ohne identische Ergebnisse zu unterstellen.
- [ ] Ausgangswerte für Bildtreue, 3D-Übereinstimmung, harte Bauplanfehler, Laufzeit und Kosten getrennt ausgewiesen.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Vergleichsbericht für die zwölf Entwicklungsfälle; keine Geheimnisse oder fremden Wohnungsfotos öffentlich ablegen.

---

### Bildqualität

<a id="b01"></a>

#### B01 · Gestaltungswunsch als prüfbare Anforderungen erfassen

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [Q01](#q01), [Q02](#q02)

**Ziel:** Ungewollte zusätzliche Objekte und verlorene Nutzerwünsche bereits an der Eingabe reduzieren.

**Lieferung:** Strukturierte Beschreibung von Möbeltyp, Form, Anzahl, Ausrichtung, Materialien, Farben und Ausschlüssen.

**Abnahme**

- [ ] Muss-Angaben, optionale Wünsche und Schätzungen getrennt erfasst.
- [ ] Widersprüchliche Anforderungen und geometrische Grenzen explizit erkannt; notwendige Rückfragen bleiben gezielt.
- [ ] Bildgenerierung und Bildbewertung verwenden dieselben Muss-Kriterien.
- [ ] Ergebnisse gegenüber dem Ausgangsstand bewertet; neue schwere Fehler werden ausgewiesen.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Anforderungsdatensätze und Vorher-/Nachher-Bilder für mindestens sechs unterschiedliche Entwicklungsfälle.

---

<a id="b02"></a>

#### B02 · Bildmodelle und Generierungseinstellungen vergleichen

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [B01](#b01)

**Ziel:** Die passende Generierungskonfiguration anhand nachweisbarer Ergebnisse auswählen.

**Lieferung:** Kontrollierter Vergleich der bestehenden Konfiguration mit ein bis zwei geeigneten Alternativen oder Parametervarianten.

**Abnahme**

- [ ] Gleiche Fotos, Masken und Anforderungen; je Versuch möglichst nur eine Einflussgröße verändert.
- [ ] Mehrere Durchläufe je Fall; Ergebnisse ohne sichtbare Modellnamen durch Philipp bewertet.
- [ ] Wunschtreue, Raumerhalt, Proportionen, Perspektive und unerwünschte Objekte getrennt erfasst.
- [ ] Qualitätsgewinn, Kosten und Laufzeit dokumentiert; Versuchsbudget vor den Aufrufen festgelegt.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Vergleichsbogen mit vollständiger Auswahl einschließlich schlechter Ergebnisse; Gewinnerkonfiguration begründet.

---

<a id="b03"></a>

#### B03 · Entwurfsbilder prüfen und gezielt korrigieren

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [B02](#b02), [O01](#o01)

**Ziel:** Entwürfe mit schweren Anforderungsverletzungen erkennen und begrenzt nachbessern.

**Lieferung:** Prüfung gegen Muss-Kriterien mit höchstens zwei Korrekturrunden und nachvollziehbarer Fehlerbegründung.

**Abnahme**

- [ ] Ungewollte Möbel, fehlende Merkmale, Raumänderungen und offensichtlich schwebende Teile getrennt geprüft.
- [ ] Erlaubte Bearbeitungszone einschließlich Übergangsrand festgelegt; Veränderungen außerhalb geprüft.
- [ ] Korrektur verändert gezielt den beanstandeten Punkt; letzter nachweislich besserer Stand bleibt erhalten.
- [ ] Automatische Urteile an menschlichen Bewertungen geprüft; ausgelassene Prüfungen gelten nicht als bestanden.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Vorher-/Nachher-Paare sowie Fehlalarme und übersehene Mängel dokumentiert.

---

### 3D-Genauigkeit und Abgleich

<a id="d01"></a>

#### D01 · 3D-Bildtreue unabhängig bewertbar machen

**P1** · Verantwortlich: **Philipp** · Gegenprüfung: **Lennart**

**Voraussetzungen:** [Q01](#q01)

**Ziel:** Äußere Ähnlichkeit und tatsächliche Geometriegenauigkeit getrennt beurteilen.

**Lieferung:** Referenzbogen für Silhouette, Proportionen, sichtbare Teile, Ausrichtung und Farbe; zusätzliche synthetische Fälle mit bekanntem 3D-Modell.

**Abnahme**

- [ ] Entwurfsbild und Modellansicht mit möglichst übereinstimmender Kamera verglichen; Kameraschätzung dokumentiert.
- [ ] Mehrere Modellansichten auf fehlende oder zusätzliche Teile geprüft.
- [ ] Bei synthetischen Referenzobjekten bekannte Abmessungen und Geometrie als Soll verwendet.
- [ ] Verdeckte Geometrie als Annahme markiert; Schätzungen aus einem Einzelbild nicht als gemessene Wahrheit bewertet.
- [ ] Gegenprüfung durch Lennart dokumentiert.

**Nachweis:** Annotierte Vergleichsbilder und Soll-Geometrien; kein alleiniger Ähnlichkeitswert für das gesamte Bild.

---

<a id="d02"></a>

#### D02 · Astra-Rekonstruktion mit Bildabgleich verbessern

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [Q02](#q02), [D01](#d01), [O01](#o01)

**Ziel:** Die bereits integrierte visuelle Szene genauer an die sichtbaren Merkmale des gewählten Bildes anpassen.

**Lieferung:** Rekonstruktion → Renderbild → Vergleich → begrenzte Szenenkorrektur.

**Abnahme**

- [ ] Sichtbare Teile, Rundungen, Neigungen, Polster und Materialfarben gegen das Bild geprüft.
- [ ] Szene aus mehreren Ansichten gerendert; Vergleich zum Original unter angeglichener Kamerapose.
- [ ] Höchstens zwei gezielte Korrekturen; unveränderte Merkmale geschützt und Verschlechterungen verworfen.
- [ ] Schemasicherheit, geometrische Plausibilität und visuelle Übereinstimmung getrennt geprüft; Verbesserung durch Philipp bestätigt.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Originalbild, bisherige Szene, korrigierte Szene und menschliche Bewertung auf denselben Fällen.

---

<a id="c01"></a>

#### C01 · Abweichungen zwischen Bild, 3D und Konstruktion abgleichen

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [B01](#b01), [D01](#d01)

**Ziel:** Verhindern, dass Vorschau und Bauplan unbemerkt unterschiedliche Möbel beschreiben.

**Lieferung:** Gemeinsame sichtbare Merkmale und messbare Vorgaben mit Herkunft; expliziter Abweichungsbericht.

**Abnahme**

- [ ] Auswahl, Maße und relevante Merkmale eindeutig zwischen Bild, visueller Szene und Konstruktionsversion verknüpft.
- [ ] Nicht unterstützte Formen erkannt, insbesondere Neigungen und Rundungen gegenüber der achsparallelen Engine.
- [ ] Wesentliche konstruktive Änderungen am Aussehen werden vor Freigabe dargestellt und vom Nutzer bestätigt.
- [ ] Bauplan und konstruktives 3D-Modell aus derselben geprüften Konstruktionsversion erzeugt; die visuelle Vorschau bleibt eigenständig.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Vergleich an mindestens einer schrägen Lehne, einer Rundung und einem Modell mit zusätzlicher Stabilisierung.

---

### Raumaufnahme und Maße

<a id="r01"></a>

#### R01 · Raumaufnahme und Maßermittlung absichern

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [Q01](#q01)

**Ziel:** Unbrauchbare Fotos und unzuverlässige Maßschätzungen früh erkennbar machen.

**Lieferung:** Aufnahmehinweise, Prüfung der Messgrundlage und bestätigte Maße vor der Konstruktion.

**Abnahme**

- [ ] Unvollständige Markierung, ungeeigneter Blickwinkel und fehlende Referenzmessung verständlich behandelt.
- [ ] Geschätzte, gemessene und manuell bestätigte Maße unterscheidbar.
- [ ] Ursachen der vorhandenen numerischen Warnungen untersucht; ungültige oder unendliche Ergebnisse abgefangen, Warnungen nicht bloß ausgeblendet.
- [ ] Vergleich mit real nachgemessenen Bereichen einschließlich dokumentierter Fehler und Ausreißer.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Messprotokoll mit realen Sollwerten und Randfällen; keine pauschale Genauigkeitszusage aus Einzelbildern.

---

### Baupläne und praktische Prüfung

<a id="p01"></a>

#### P01 · Fehlerhafte Baupläne vor Export sperren

**P0** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** keine

**Ziel:** Konstruktionen mit bekannten kritischen Fehlern nicht als baubereiten Plan ausgeben.

**Lieferung:** Verbindliche Freigaberegel für Bauplanansicht, PDF und DXF.

**Abnahme**

- [ ] Kritische Fehler von Hinweisen unterschieden: fehlende tragende Verbindung, fehlendes Auflager, unzulässige Tragfähigkeitsausnutzung und relevante Kollisionen.
- [ ] PDF und DXF werden bei kritischen Fehlern serverseitig blockiert; direkte API-Aufrufe berücksichtigen dieselbe Regel.
- [ ] Ursache und nächster sinnvoller Schritt werden angezeigt; visuelle Vorschau bleibt als solche erkennbar.
- [ ] Positive und negative Referenzfälle geprüft; ein grüner Regressionstest allein gilt nicht als Baubarkeitsnachweis.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** API-Tests mit absichtlich fehlerhaften Modellen + freigegebenem Gegenbeispiel. Die Engine bleibt eine Vorbemessung.

---

<a id="p02"></a>

#### P02 · Zuschnitt, Verbindungen und Montage konsistent prüfen

**P0** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [P01](#p01)

**Ziel:** Aus derselben Konstruktion widerspruchsfreie Einkaufsliste, Zuschnitte und Montage erzeugen.

**Lieferung:** Prüfungen für Materialmengen, Handelslängen, Verbindungen und ausführbare Montageschritte.

**Abnahme**

- [ ] Jedes tragende Teil hat geometrisch passende Auflager beziehungsweise definierte Verbindungen.
- [ ] Zuschnitt und Einkauf decken alle Teile und benötigten Beschläge ab; kein Teil überschreitet verfügbare Rohmaße.
- [ ] Montagereihenfolge berücksichtigt Zugänglichkeit der Schrauben und bereits verbaute Teile.
- [ ] Fehler werden als Negativfälle getestet; Maße, Teilekennungen und Mengen stimmen in JSON, PDF und 3D überein.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Mindestens drei vollständige Referenzpläne mit manueller Gegenrechnung und absichtlich fehlerhaften Gegenbeispielen.

---

<a id="p03"></a>

#### P03 · Fachliche Prüfung und dokumentierten Testbau organisieren

**P0** · Verantwortlich: **Philipp** · Gegenprüfung: **Lennart**

**Voraussetzungen:** [P02](#p02), [C01](#c01)

**Ziel:** Die rechnerische Vorbemessung durch unabhängige praktische Prüfung ergänzen.

**Lieferung:** Fachprüfung eines einfachen Pilotmöbels und dokumentierter Testbau unter fachlicher Begleitung.

**Abnahme**

- [ ] Qualifizierte Person für Konstruktion, Verbindungen und relevante Belastungsannahmen benannt.
- [ ] Plan vor Materialkauf geprüft; Beanstandungen in konkrete Korrekturkarten überführt.
- [ ] Montagefragen, fehlende Angaben, Maßabweichungen und notwendige improvisierte Schritte protokolliert.
- [ ] Pilotfreigabe bezieht sich ausdrücklich auf das geprüfte Modell und die geprüften Randbedingungen.
- [ ] Gegenprüfung durch Lennart dokumentiert.

**Nachweis:** Kommentierter Plan, Bauprotokoll, Fotos und begründete fachliche Freigabe; keine Übertragung auf beliebige Möbel.

---

### Kosten, Projekte und Wiederherstellung

<a id="o01"></a>

#### O01 · Kosten- und Wiederholungsgrenzen atomar absichern

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** keine

**Ziel:** Mehrfachklicks und parallele Korrekturrunden dürfen das Testbudget nicht unkontrolliert verbrauchen.

**Lieferung:** Atomare Reservierung und idempotente Aufträge für Bild- und 3D-Aufrufe.

**Abnahme**

- [ ] Prüfung und Buchung des Kontingents sind gegen parallele Zugriffe abgesichert.
- [ ] Doppelte Anfragen derselben Aktion erzeugen keinen zweiten bezahlten Auftrag.
- [ ] Maximale Korrekturrunden und Gesamtbudget eines Durchgangs gelten auch bei Fehlern und Wiederholungen.
- [ ] Parallele Grenzfälle reproduziert; geschätzte Reservierungen und tatsächliche Kosten soweit verfügbar getrennt protokolliert.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Paralleltests und Kostenprotokoll; reproduzierbaren bisherigen Kontingentfehler als Regressionstest aufnehmen.

---

<a id="o02"></a>

#### O02 · Projektversionen und laufende Aufträge wiederherstellen

**P2** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [C01](#c01)

**Ziel:** Ergebnisse und ihre Zuordnung nach App-Wechsel oder Serverneustart zuverlässig erhalten.

**Lieferung:** Gespeicherte Projektstände und kontrolliert wiederaufnehmbare Hintergrundaufträge.

**Abnahme**

- [ ] Raumfoto, Auswahl, visuelle Szene und Konstruktionsversion dauerhaft und eindeutig zugeordnet.
- [ ] App-Neustart stellt den zuletzt gespeicherten Projektstand her.
- [ ] Serverneustart führt zu Wiederaufnahme oder explizitem Fehler statt unbegrenzt laufendem Status.
- [ ] Bereits vorhandene Ergebnisse werden wiederverwendet; keine doppelte Kostenbuchung bei Wiederherstellung.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Unterbrechungstests mit App-Neustart, Verbindungsabbruch und Worker-Neustart.

---

### Abnahme und Nutzertests

<a id="t01"></a>

#### T01 · Zurückgehaltene Fälle blind abnehmen

**P1** · Verantwortlich: **Philipp** · Gegenprüfung: **Lennart**

**Voraussetzungen:** [B03](#b03), [D02](#d02), [C01](#c01), [P02](#p02)

**Ziel:** Prüfen, ob die Verbesserung über die optimierten Beispiele hinaus trägt.

**Lieferung:** Auswertung der acht zurückgehaltenen Fälle mit anonymisierten Vorher-/Nachher-Ergebnissen.

**Abnahme**

- [ ] Fälle vorab unverändert festgelegt; keine Promptoptimierung anhand der Abnahmeergebnisse vor der Bewertung.
- [ ] Bildqualität, 3D-Treue und Bauplankonsistenz unabhängig bewertet.
- [ ] Alle schweren Fehler einzeln ausgewiesen; schönerer Gesamteindruck kompensiert keinen Konstruktionsfehler.
- [ ] Bei Anpassungen nach der Abnahme neue unabhängige Fälle ergänzen; kleine Stichprobe als begrenzte Evidenz kennzeichnen.
- [ ] Gegenprüfung durch Lennart dokumentiert.

**Nachweis:** Blindbewertung mit Fallzahlen, Fehlerlisten und Entscheidung: freigeben, korrigieren oder Umfang begrenzen.

---

<a id="t02"></a>

#### T02 · Den gesamten iOS-Ablauf mit fünf Personen testen

**P1** · Verantwortlich: **Philipp** · Gegenprüfung: **Lennart**

**Voraussetzungen:** [T01](#t01), [O02](#o02)

**Ziel:** Prüfen, ob Nutzer die Ergebnisse verstehen und Abweichungen rechtzeitig erkennen.

**Lieferung:** Fünf beobachtete Tests: eigenes Foto → Wunsch → Entwurf → 3D → Bauplanansicht.

**Abnahme**

- [ ] Aufgabe ohne erklärende Hilfestellung durchgeführt; Abbrüche und Rückfragen dokumentiert.
- [ ] Teilnehmer unterscheiden Entwurfsbild, visuelle Annäherung und geprüfte Konstruktionsansicht.
- [ ] Hinweise zu geschätzten Maßen und konstruktiven Änderungen werden verstanden.
- [ ] Schwerwiegende Missverständnisse jeweils als eigene Karte erfasst; keine Bauausführung durch Testpersonen ohne vorherige fachliche Freigabe.
- [ ] Gegenprüfung durch Lennart dokumentiert.

**Nachweis:** Anonymisierte Beobachtungsnotizen und priorisierte Probleme; fünf Tests sind keine statistische Wirksamkeitsstudie.

---

<a id="q03"></a>

#### Q03 · Qualitätsabnahme vor jeder Veröffentlichung verankern

**P1** · Verantwortlich: **Lennart** · Gegenprüfung: **Philipp**

**Voraussetzungen:** [T01](#t01), [P03](#p03)

**Ziel:** Einmal erzielte Verbesserungen bei Modell-, Prompt- und Codeänderungen nachvollziehbar erhalten.

**Lieferung:** Versionierte Abnahmekriterien, Regressionen und eine verbindliche Freigabeentscheidung.

**Abnahme**

- [ ] Qualitätsbericht und Referenzfälle jeder Modell- oder Promptänderung zugeordnet.
- [ ] Keine Freigabe bei bekannten kritischen Konstruktionsfehlern oder neu eingeführten schweren Regressionen.
- [ ] Bild- und 3D-Zielwerte anhand der Ausgangsmessung gemeinsam festgelegt; keine willkürliche Erfolgsbehauptung.
- [ ] Gegenprüfung durch den jeweils anderen dokumentiert; fachliche Freigabe zusätzlich, wo konstruktiv erforderlich.
- [ ] Gegenprüfung durch Philipp dokumentiert.

**Nachweis:** Freigabeprotokoll mit Versionen, Grenzen, bekannten Restfehlern und verantwortlicher Entscheidung.

---

<a id="kartenvorlage"></a>

## 6. Vorlage für neue Karten

Diesen Block als Trello-Kartenvorlage verwenden. Das Ergebnisprotokoll gilt auch für die bestehenden 17 Karten.

```markdown
# [Priorität] ID · konkretes Ergebnis

**Verantwortlich:** eine Person
**Gegenprüfung:** andere Person
**Bereich:** Arbeitsbereich
**Voraussetzungen:** Karten-IDs oder „keine“

## Ziel
Welcher beobachtete Fehler oder welches Qualitätsproblem wird gelöst?

## Lieferung
Welches konkrete, überprüfbare Ergebnis entsteht?

## Abnahme

- [ ] Kriterien erfüllt und negative Fälle geprüft.
- [ ] Vorher-/Nachher-Nachweise mit identischen Referenzfällen angehängt.
- [ ] Kosten, Laufzeit und Restgrenzen dokumentiert.
- [ ] Gegenprüfung dokumentiert.

## Nachweis
Vergleichsbilder, Prüfbericht, Tests oder andere überprüfbare Belege.

## Ergebnisprotokoll

- **Version / Fall-IDs:**
- **Vorher / nachher:**
- **Schwere Fehler / Restgrenzen:**
- **Entscheidung der Gegenprüfung:**
```

---

<a id="quellen"></a>

## 7. Ausgangspunkt und Quellen

### Technischer Ausgangspunkt dieser Planung

- **Getrennte Rekonstruktionen:** Visuelle Vorschau und konstruktive Ausarbeitung sind getrennt; die Konstruktion verwendet erneut das Entwurfsbild. Siehe [Projektbeschreibung](/Users/lennartlunt/Developer/Projekte/parawerk/README.md), Abschnitt „Visuelle 3D-Vorschau in der App“.
- **Geometrische Grenze:** Der Konstruktionsprompt beschreibt schräge Teile ausdrücklich achsparallel. Siehe [Konstruktionsprompt](/Users/lennartlunt/Developer/Projekte/parawerk/app/services/prompts.py), Funktion `lese_prompt`.
- **Teststand der bisherigen Arbeit:** 254 bestandene Python-Tests. Das belegt keine quantifizierte Bildtreue oder allgemeine konstruktive Verlässlichkeit. Eine Live-Abnahme der Astra-Bildtreue wurde in dieser Arbeit noch nicht vorgenommen.

### Methodik und Trello-Funktionen

- [OpenAI · Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices): spezifische Kriterien, menschliche Kalibrierung und laufende Regressionsevaluation.
- [Trello · Personen einer Karte zuordnen](https://support.atlassian.com/trello/docs/adding-a-member-to-a-card/).
- [Trello · Checklisten verwalten](https://support.atlassian.com/trello/docs/adding-checklists-to-cards/).

### Übernahme in Trello

1. Die fünf Listen aus [Abschnitt 3](#zusammenarbeit) anlegen.
2. Die Karten aus [Abschnitt 5](#karten) mit Titel, Beschreibung und Checkliste übernehmen.
3. Verantwortliche, Prioritätslabel und Abhängigkeiten ergänzen.
4. Q01, P01 und anschließend Q02 für den ersten Arbeitsdurchgang einplanen.

Die Vorlage setzt Listen, Mitglieder, Labels, Beschreibungen und einfache Checklisten voraus. Zusatzfelder oder kostenpflichtige Zusatzfunktionen sind dafür nicht erforderlich. **Dies ist eine Kopiervorlage, keine native Trello-Importdatei.**
