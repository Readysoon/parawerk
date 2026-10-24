# Parawerk-App (Flutter)

Die App fotografiert, lässt den Bereich markieren und zeigt Entwürfe, Bauplan und 3D-Modell. Alles Rechnen und die Bildarbeit macht der Server über `/api/v1` (siehe README im Hauptordner).

## Einrichten (einmal)

Voraussetzungen: Flutter, Xcode (für iPhone), Android Studio (für Android). `flutter doctor` sollte keine roten Punkte zeigen.

```bash
cd mobile
./einrichten.sh
```

Das legt die Ordner `ios/` und `android/` an, trägt die Berechtigungen für Kamera, Fotos und Internet ein und prüft den Code (`flutter analyze`). Die neuen Ordner danach mit committen.

## Starten

```bash
flutter run                      # wählt ein angeschlossenes Handy oder einen Simulator
flutter run -d ios               # iPhone-Simulator (vorher: open -a Simulator)
```

Gegen einen Server auf dem eigenen Rechner statt parawerk.fly.dev:
```bash
flutter run --dart-define=API=http://192.168.1.20:8000
```

## Aufbau

```
lib/
  main.dart            Start, Sprache (Deutsch auf deutschen Geräten, sonst Englisch)
  api.dart             Server-Aufrufe, Aufträge abfragen, Geräte-ID
  sitzung.dart         Foto, Maske, Maße, Wunsch, Antworten des Servers
  malflaeche.dart      Foto mit dem Finger markieren, Maske als PNG
  texte.dart           Texte Deutsch/Englisch
  hilfen.dart          Wartedialog, Hinweise
  seiten/              Start → Markieren → Wunsch → Entwürfe → Bauplan
```

Noch nicht in der App (gibt es auf der Website): A4-Maßstab, Bereich nachträglich ändern, DXF-Download, Konto und Bezahlung.
