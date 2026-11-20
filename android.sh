#!/bin/bash
# Parawerk für Android. Voraussetzung: Android Studio installiert (bringt das Android-SDK mit), einmal geöffnet.
#
#   bash android.sh testen      App auf dem Android-Handy (USB-Debugging an) mit dem Server auf diesem Mac
#   bash android.sh schluessel  einmalig: eigenen Schlüssel zum Signieren für Google Play anlegen
#   bash android.sh fingerabdruck  SHA-1-Fingerabdrücke anzeigen (für die Google-Anmeldung in der Google Cloud Console)
#   bash android.sh bauen       Version für Google Play bauen (.aab-Datei zum Hochladen in der Play Console)
set -e
cd ~/Web_Projects/parawerk

# Google-Anmeldung auf Android braucht die Web-Client-ID (aus .env)
WEB_ID=$(grep '^GOOGLE_WEB_CLIENT_ID=' .env 2>/dev/null | cut -d= -f2-)
DEFINES="--dart-define=SPRACHE=de"
[ -n "$WEB_ID" ] && DEFINES="$DEFINES --dart-define=GOOGLE_WEB_CLIENT_ID=$WEB_ID"

patches_einspielen() {
  for p in $(ls -tr *.patch 2>/dev/null); do
    if [ -f "$p" ]; then git am "$p" && rm "$p" && echo "✓ $p eingespielt"; fi
  done
}

case "$1" in
  testen)
    patches_einspielen
    grep -q '^LIMITS=' .env || echo 'LIMITS=false' >> .env
    IP=$(ifconfig | awk '/inet 172\.20\.10\./{print $2; exit}')
    [ -z "$IP" ] && IP=$(ipconfig getifaddr en0 || ipconfig getifaddr en1 || true)
    if [ -z "$IP" ]; then echo "Kein Netz gefunden. Ist der Mac im WLAN oder im Hotspot?"; exit 1; fi
    echo "✓ Mac im Netz: $IP"
    UVICORN=uvicorn; [ -x .venv/bin/uvicorn ] && UVICORN=.venv/bin/uvicorn
    $UVICORN app.main:app --host 0.0.0.0 --port 8000 > /tmp/parawerk-server.log 2>&1 &
    SERVER=$!; trap 'kill $SERVER 2>/dev/null' EXIT; sleep 3
    echo "✓ Server läuft (Log: /tmp/parawerk-server.log)"
    cd mobile
    GERAET=$(flutter devices --machine 2>/dev/null | python3 -c "import json,sys;d=[x for x in json.load(sys.stdin) if x.get('targetPlatform','').startswith('android')];print(d[0]['id'] if d else '')")
    if [ -z "$GERAET" ]; then echo "Kein Android-Handy gefunden. USB-Debugging an? Kabel dran? „Zulassen“ auf dem Handy getippt?"; exit 1; fi
    flutter run -d "$GERAET" --dart-define=API=http://$IP:8000 $DEFINES
    ;;

  schluessel)
    DATEI=~/parawerk-upload.jks
    if [ -f "$DATEI" ]; then echo "Schlüssel gibt es schon: $DATEI"; exit 0; fi
    read -r -s -p "Neues Passwort für den Schlüssel (mind. 6 Zeichen, gut aufheben!): " PW; echo
    keytool -genkeypair -v -keystore "$DATEI" -storetype JKS -keyalg RSA -keysize 2048 -validity 10000 \
      -alias upload -storepass "$PW" -keypass "$PW" -dname "CN=Parawerk, O=Parawerk, C=AT"
    printf 'storeFile=%s\nstorePassword=%s\nkeyAlias=upload\nkeyPassword=%s\n' "$DATEI" "$PW" "$PW" > mobile/android/key.properties
    chmod 600 mobile/android/key.properties "$DATEI"
    echo "✓ Schlüssel: $DATEI (nicht im Projekt, nicht im Git). Bitte zusätzlich sichern, z. B. im Passwortmanager."
    echo "  Geht er verloren, kann man bei Google Play nur über den Support einen neuen hinterlegen."
    ;;

  fingerabdruck)
    echo "== Test-Schlüssel (flutter run):"
    keytool -list -v -keystore ~/.android/debug.keystore -alias androiddebugkey -storepass android 2>/dev/null | grep 'SHA1:' || echo "noch keiner – einmal 'bash android.sh testen' starten"
    if [ -f ~/parawerk-upload.jks ]; then
      echo "== Eigener Schlüssel (Google Play Upload):"
      PW=$(grep storePassword mobile/android/key.properties | cut -d= -f2-)
      keytool -list -v -keystore ~/parawerk-upload.jks -alias upload -storepass "$PW" | grep 'SHA1:'
    fi
    echo "Dazu kommt nach dem ersten Hochladen der Fingerabdruck aus der Play Console (App-Signatur)."
    ;;

  bauen)
    patches_einspielen
    if [ ! -f mobile/android/key.properties ]; then echo "Erst einmal: bash android.sh schluessel"; exit 1; fi
    [ -z "$WEB_ID" ] && echo "Hinweis: GOOGLE_WEB_CLIENT_ID fehlt in .env – die Google-Anmeldung geht dann auf Android nicht."
    git push
    ALT=$(grep '^version:' mobile/pubspec.yaml | sed 's/.*+//'); NEU=$((ALT + 1))
    sed -i '' "s/^version: \(.*\)+$ALT$/version: \1+$NEU/" mobile/pubspec.yaml
    git add mobile/pubspec.yaml && git commit -q -m "Build $NEU (Android)" && git push -q
    echo "✓ Build-Nummer $NEU"
    cd mobile
    flutter build appbundle --release $DEFINES
    echo "✓ Fertig: mobile/build/app/outputs/bundle/release/app-release.aab"
    echo "  Hochladen: play.google.com/console → Parawerk → Testen → Interner Test → Neuer Release"
    open build/app/outputs/bundle/release/
    ;;

  *)
    sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'
    ;;
esac
