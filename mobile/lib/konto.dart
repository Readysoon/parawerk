// Konto: „Mit Apple anmelden“ und „Mit Google anmelden“. Der Server prüft das ID-Token des Anbieters.
// Ein Konto braucht man fürs Anpassen, für weitere Runden und fürs Umwandeln in einen Bauplan (wenn eingeschaltet).
import 'dart:io' show Platform;

import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import 'api.dart';
import 'texte.dart';

/// OAuth-Client-IDs von Google (Google Cloud Console), beim Bauen mitgeben:
/// flutter build ipa --dart-define=GOOGLE_IOS_CLIENT_ID=… --dart-define=GOOGLE_WEB_CLIENT_ID=…
const _googleIos = String.fromEnvironment('GOOGLE_IOS_CLIENT_ID');
const _googleWeb = String.fromEnvironment('GOOGLE_WEB_CLIENT_ID');

Future<String?> _mitApple(Api api) async {
  final c = await SignInWithApple.getAppleIDCredential(scopes: [AppleIDAuthorizationScopes.email]);
  final token = c.identityToken;
  if (token == null) return null;
  return api.anmelden('apple', token, email: c.email);
}

Future<String?> _mitGoogle(Api api) async {
  final google = GoogleSignIn(
    scopes: const ['email'],
    clientId: Platform.isIOS && _googleIos.isNotEmpty ? _googleIos : null,
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

class _AnmeldeBlatt extends StatefulWidget {
  const _AnmeldeBlatt({required this.api, this.grund});
  final Api api;
  final String? grund;

  @override
  State<_AnmeldeBlatt> createState() => _AnmeldeBlattState();
}

class _AnmeldeBlattState extends State<_AnmeldeBlatt> {
  bool _laeuft = false;
  String? _fehler;

  Future<void> _los(Future<String?> Function(Api) anmelden) async {
    setState(() {
      _laeuft = true;
      _fehler = null;
    });
    try {
      final name = await anmelden(widget.api);
      if (!mounted) return;
      if (name != null) Navigator.of(context).pop(true);
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
    final stil = Theme.of(context).textTheme;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Text(tr('konto_titel'), style: stil.titleLarge),
          const SizedBox(height: 8),
          Text(widget.grund ?? tr('konto_warum'), style: stil.bodyMedium),
          const SizedBox(height: 20),
          if (Platform.isIOS) ...[
            SignInWithAppleButton(
              text: tr('mit_apple'),
              height: 48,
              onPressed: _laeuft ? () {} : () => _los(_mitApple),
            ),
            const SizedBox(height: 12),
          ],
          OutlinedButton.icon(
            onPressed: _laeuft ? null : () => _los(_mitGoogle),
            icon: const Icon(Icons.account_circle_outlined),
            label: Text(tr('mit_google')),
            style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          ),
          if (_laeuft) const Padding(padding: EdgeInsets.only(top: 16), child: Center(child: CircularProgressIndicator())),
          if (_fehler != null)
            Padding(padding: const EdgeInsets.only(top: 12), child: Text(_fehler!, style: const TextStyle(color: Colors.red))),
          const SizedBox(height: 8),
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: Text(tr('abbrechen'))),
        ]),
      ),
    );
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
