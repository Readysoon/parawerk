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

Gegen einen Server auf dem eigenen Rechner statt parawerk.fly.dev (Handy und Mac im selben WLAN):
```bash
ipconfig getifaddr en0                                   # IP des Macs, z. B. 192.168.1.20
uvicorn app.main:app --reload --host 0.0.0.0             # im Projektordner: Server fürs WLAN öffnen
flutter run --dart-define=API=http://192.168.1.20:8000 --dart-define=SPRACHE=de
```
Beim ersten Start fragt iOS nach „Lokales Netzwerk“: erlauben. Apple- und Google-Anmeldung gehen auch lokal
(mit `GOOGLE_CLIENT_IDS` in `.env`), die Demo-Anmeldung nur mit `STUFEN_SIMULIEREN=true`.

## Android

Alles über `android.sh` im Hauptordner (Android Studio muss installiert sein):
```bash
bash android.sh testen          # Android-Handy per USB (USB-Debugging an), Server auf dem Mac
bash android.sh schluessel      # einmalig: Signier-Schlüssel ~/parawerk-upload.jks + android/key.properties
bash android.sh fingerabdruck   # SHA-1 für den Android-OAuth-Client in der Google Cloud Console
bash android.sh bauen           # .aab für Google Play (Interner Test)
```
- Google-Anmeldung braucht auf Android einen **Android-Client** (Paket `at.parawerk.parawerk` + SHA-1) und einen
  **Web-Client** in der Google Cloud Console. Die Web-Client-ID kommt als `GOOGLE_WEB_CLIENT_ID` in `.env` und in
  die fly secrets; der Server nimmt sie automatisch zu den erlaubten IDs dazu.
- AR läuft auf Android über Googles Scene Viewer. Der lädt das Modell selbst aus dem Netz, geht also nur mit dem
  Server online (parawerk.fly.dev), nicht mit dem Server auf dem Mac.
- Apple-Anmeldung gibt es nur auf dem iPhone.

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
