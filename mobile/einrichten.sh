#!/bin/bash
# Einmal ausführen (auf dem Mac, im Ordner mobile/): legt die iOS- und Android-Projekte an
# und trägt die nötigen Berechtigungen ein. Der App-Code in lib/ bleibt unverändert.
set -e
cd "$(dirname "$0")"

flutter create . --platforms=ios,android --org at.parawerk --project-name parawerk

# iOS: Texte für Kamera und Fotos (ohne sie stürzt die App beim Fotografieren ab)
PLIST=ios/Runner/Info.plist
plutil -replace NSCameraUsageDescription -string "Parawerk braucht die Kamera, um die Ecke zu fotografieren, in die das Möbel soll." "$PLIST"
plutil -replace NSPhotoLibraryUsageDescription -string "Parawerk braucht Zugriff auf deine Fotos, um ein Foto der Ecke auszuwählen." "$PLIST"
# Nur Standard-HTTPS, keine eigene Verschlüsselung: Apple fragt dann nicht bei jedem Build nach
plutil -replace ITSAppUsesNonExemptEncryption -bool NO "$PLIST"

# Mit Google anmelden (iOS): die umgekehrte iOS-Client-ID als URL-Schema, sonst kommt man nach der Anmeldung nicht zurück.
# Aufruf: GOOGLE_IOS_CLIENT_ID=123-abc.apps.googleusercontent.com ./einrichten.sh
if [ -n "$GOOGLE_IOS_CLIENT_ID" ]; then
  SCHEMA="com.googleusercontent.apps.${GOOGLE_IOS_CLIENT_ID%.apps.googleusercontent.com}"
  plutil -replace GIDClientID -string "$GOOGLE_IOS_CLIENT_ID" "$PLIST"
  plutil -replace CFBundleURLTypes -json "[{\"CFBundleURLSchemes\":[\"$SCHEMA\"]}]" "$PLIST"
fi
# Mit Apple anmelden: die Fähigkeit „Sign in with Apple“ einmal in Xcode hinzufügen
# (Runner → Signing & Capabilities → + Capability → Sign in with Apple).

# Android: Internet (für den Server) und lokale Verbindung für die 3D-Anzeige
MANIFEST=android/app/src/main/AndroidManifest.xml
grep -q 'android.permission.INTERNET' "$MANIFEST" || \
  perl -0pi -e 's#<application#<uses-permission android:name="android.permission.INTERNET"/>\n    <application#' "$MANIFEST"
grep -q 'usesCleartextTraffic' "$MANIFEST" || \
  perl -0pi -e 's#<application#<application android:usesCleartextTraffic="true"#' "$MANIFEST"

flutter pub get
flutter analyze --no-fatal-infos
echo "Fertig. Starten mit: flutter run"
