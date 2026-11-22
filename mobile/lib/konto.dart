// Konto: „Mit Apple anmelden“ und „Mit Google anmelden“. Der Server prüft das ID-Token des Anbieters.
// Ein Konto braucht man fürs Anpassen, für weitere Runden und fürs Umwandeln in einen Bauplan (wenn eingeschaltet).
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import 'api.dart';
import 'hilfen.dart';
import 'sitzung.dart';
import 'texte.dart';

/// OAuth-Client-IDs von Google (Google Cloud Console), beim Bauen mitgeben:
/// flutter build ipa --dart-define=GOOGLE_IOS_CLIENT_ID=… --dart-define=GOOGLE_WEB_CLIENT_ID=…
const _googleIos = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');
const _googleWeb = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');

bool get _iPhone => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;

/// Nur wenn der Server im Demo-Modus läuft (lokal, ohne KI-Schlüssel): Anmelden ohne Apple/Google.
Future<String?> _mitDemo(Api api) => api.anmelden('demo', 'demo-nutzer-${api.geraet}');

Future<String?> _mitApple(Api api) async {
  final c = await SignInWithApple.getAppleIDCredential(scopes: [AppleIDAuthorizationScopes.email]);
  final token = c.identityToken;
  if (token == null) return null;
  return api.anmelden('apple', token, email: c.email);
}

Future<String?> _mitGoogle(Api api) async {
  final google = GoogleSignIn(
    scopes: const ['email'],
    clientId: _iPhone && _googleIos.isNotEmpty ? _googleIos : null,
    serverClientId: _googleWeb.isNotEmpty ? _googleWeb : null,
  );
  final konto = await google.signIn();
  if (konto == null) return null; // abgebrochen
  final token = (await konto.authentication).idToken;
  if (token == null) return null;
  return api.anmelden('google', token);
}

/// Zeigt die Anmeldung als Blatt von unten. true = angemeldet.
Future<bool> anmeldenFragen(BuildContext context, {String? grund}) async {
  final api = Api.aktuell;
  if (api == null) return false;
  final ok = await showModalBottomSheet<bool>(
    context: context,
    isScrollControlled: true,
    builder: (ctx) => _AnmeldeBlatt(api: api, grund: grund),
  );
  return ok == true;
}

class _AnmeldeBlatt extends StatelessWidget {
  const _AnmeldeBlatt({required this.api, this.grund});
  final Api api;
  final String? grund;

  @override
  Widget build(BuildContext context) {
    final stil = Theme.of(context).textTheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(tr('konto_titel'), style: stil.titleLarge),
          const SizedBox(height: 8),
          Text(grund ?? tr('konto_warum'), style: stil.bodyMedium),
          const SizedBox(height: 20),
          AnmeldeKnoepfe(api: api, angemeldet: () => Navigator.of(context).pop(true)),
          const SizedBox(height: 8),
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(tr('abbrechen'))),
        ]),
      ),
    );
  }
}

/// Die Anmelde-Knöpfe: Apple (iPhone), Google, und nur wenn der Server es erlaubt (lokal/Demo-Modus) „Demo“.
/// Nach erfolgreicher Anmeldung wird [angemeldet] aufgerufen; die Sitzung liegt dann in der [Api].
class AnmeldeKnoepfe extends StatefulWidget {
  const AnmeldeKnoepfe({super.key, required this.api, required this.angemeldet});
  final Api api;
  final VoidCallback angemeldet;

  @override
  State<AnmeldeKnoepfe> createState() => _AnmeldeKnoepfeState();
}

class _AnmeldeKnoepfeState extends State<AnmeldeKnoepfe> {
  bool _laeuft = false;
  String? _fehler;
  bool _demo = false;

  @override
  void initState() {
    super.initState();
    widget.api.konto().then((s) {
      if (mounted) setState(() => _demo = s.demo);
    }).catchError((_) {});
  }

  Future<void> _los(Future<String?> Function(Api) anmelden) async {
    setState(() {
      _laeuft = true;
      _fehler = null;
    });
    try {
      final name = await anmelden(widget.api);
      if (!mounted) return;
      if (name != null) widget.angemeldet();
    } on SignInWithAppleAuthorizationException catch (e) {
      if (e.code != AuthorizationErrorCode.canceled && mounted) setState(() => _fehler = tr('anmelden_fehler'));
    } catch (e) {
      if (mounted) setState(() => _fehler = '${tr('anmelden_fehler')} ($e)');
    } finally {
      if (mounted) setState(() => _laeuft = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final google = !kIsWeb || _googleWeb.isNotEmpty;
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      if (_iPhone) ...[
        SignInWithAppleButton(
          text: tr('mit_apple'),
          height: 48,
          onPressed: _laeuft ? () {} : () => _los(_mitApple),
        ),
        const SizedBox(height: 12),
      ],
      if (google) ...[
        OutlinedButton.icon(
          onPressed: _laeuft ? null : () => _los(_mitGoogle),
          icon: const Icon(Icons.account_circle_outlined),
          label: Text(tr('mit_google')),
          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
        ),
        const SizedBox(height: 12),
      ],
      if (_demo)
        OutlinedButton.icon(
          onPressed: _laeuft ? null : () => _los(_mitDemo),
          icon: const Icon(Icons.science_outlined),
          label: Text(tr('mit_demo')),
          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
        ),
      if (!_iPhone && !google && !_demo) Text(tr('anmelden_hier_nicht')),
      if (_laeuft) const Padding(padding: EdgeInsets.only(top: 16), child: Center(child: CircularProgressIndicator())),
      if (_fehler != null)
        Padding(padding: const EdgeInsets.only(top: 12), child: Text(_fehler!, style: const TextStyle(color: Colors.red))),
    ]);
  }
}

/// Knopf oben rechts: anmelden, oder angemeldet als … mit Abmelden und Konto löschen.
class KontoKnopf extends StatefulWidget {
  const KontoKnopf({super.key, required this.api});
  final Api api;

  @override
  State<KontoKnopf> createState() => _KontoKnopfState();
}

class _KontoKnopfState extends State<KontoKnopf> {
  KontoStand? _stand;

  @override
  void initState() {
    super.initState();
    _laden();
  }

  Future<void> _laden() async {
    try {
      final s = await widget.api.konto();
      if (mounted) setState(() => _stand = s);
    } catch (_) {}
  }

  Future<void> _loeschen() async {
    final sicher = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(tr('konto_loeschen')),
        content: Text(tr('konto_loeschen_frage')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(tr('abbrechen'))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text(tr('konto_loeschen'))),
        ],
      ),
    );
    if (sicher != true) return;
    await widget.api.kontoLoeschen();
    await _laden();
  }

  @override
  Widget build(BuildContext context) {
    final s = _stand;
    if (s == null || (!s.kontoPflicht && s.email == null)) return const SizedBox.shrink();
    if (s.email == null) {
      return TextButton(
        onPressed: () async {
          if (await anmeldenFragen(context)) await _laden();
        },
        child: Text(tr('anmelden')),
      );
    }
    return PopupMenuButton<String>(
      icon: const Icon(Icons.account_circle),
      onSelected: (w) async {
        if (w == 'ab') {
          await widget.api.abmelden();
          await _laden();
        } else if (w == 'loeschen') {
          await _loeschen();
        }
      },
      itemBuilder: (_) => [
        PopupMenuItem(enabled: false, child: Text(s.email!)),
        PopupMenuItem(value: 'ab', child: Text(tr('abmelden'))),
        PopupMenuItem(value: 'loeschen', child: Text(tr('konto_loeschen'))),
      ],
    );
  }
}

/// Unten auf der Startseite: „Datenschutz“ mit Meine Daten herunterladen und Meine Daten löschen.
/// Immer sichtbar, auch ohne Konto (DSGVO Art. 15, 17, 20).
class DatenschutzKnopf extends StatelessWidget {
  const DatenschutzKnopf({super.key, required this.api});
  final Api api;

  Future<void> _herunterladen(BuildContext context) async {
    final hinweise = ScaffoldMessenger.of(context);
    final box = context.findRenderObject() as RenderBox?;
    try {
      final daten = await api.meineDaten();
      await Share.shareXFiles(
        [XFile.fromData(daten, mimeType: 'application/json', name: 'parawerk-meine-daten.json')],
        fileNameOverrides: ['parawerk-meine-daten.json'],
        sharePositionOrigin: box == null ? null : box.localToGlobal(Offset.zero) & box.size, // iPad braucht das
      );
    } catch (e) {
      hinweise.showSnackBar(SnackBar(content: Text(fehlerText(e))));
    }
  }

  Future<void> _loeschen(BuildContext context) async {
    final hinweise = ScaffoldMessenger.of(context);
    final sicher = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(tr('daten_loeschen')),
        content: Text(tr(api.angemeldet ? 'daten_loeschen_frage_konto' : 'daten_loeschen_frage')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(tr('abbrechen'))),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: Text(tr('loeschen'))),
        ],
      ),
    );
    if (sicher != true) return;
    try {
      await api.meineDatenLoeschen();
      Sitzung.letzte.value = null; // auch die Entwürfe im Speicher der App vergessen
      hinweise.showSnackBar(SnackBar(content: Text(tr('daten_geloescht'))));
    } catch (e) {
      hinweise.showSnackBar(SnackBar(content: Text(fehlerText(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopupMenuButton<String>(
      tooltip: tr('datenschutz'),
      onSelected: (w) => switch (w) {
        'erklaerung' => launchUrl(Uri.parse('$apiBasis/datenschutz'), mode: LaunchMode.inAppBrowserView),
        'herunterladen' => _herunterladen(context),
        _ => _loeschen(context),
      },
      itemBuilder: (_) => [
        PopupMenuItem(value: 'erklaerung', child: Text(tr('datenschutzerklaerung'))),
        PopupMenuItem(value: 'herunterladen', child: Text(tr('daten_herunterladen'))),
        PopupMenuItem(value: 'loeschen', child: Text(tr('daten_loeschen'))),
      ],
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          const Icon(Icons.privacy_tip_outlined, size: 18),
          const SizedBox(width: 6),
          Text(tr('datenschutz')),
        ]),
      ),
    );
  }
}

