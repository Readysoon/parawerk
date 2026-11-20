// 3D-Modell anzeigen: derselbe Viewer wie auf der Website (Seite /ansicht), eingebettet als Webfenster.
// Die App schickt nur die Teile als Daten hinein, darum kann das Modell beim Strecken live mitwachsen.
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'api.dart';
import 'modell_web_ersatz.dart' if (dart.library.js_interop) 'modell_web.dart';
import 'texte.dart';

/// Im Browser ein iframe, sonst ein Webfenster (webview_flutter gibt es im Browser nicht).
class ModellAnsicht extends StatelessWidget {
  // Zerlegen und Verzerren bedient man in der Leiste der 3D-Ansicht selbst (viewer3d.js).
  const ModellAnsicht({super.key, required this.modell, this.kameraHalten = false, this.seitenverhaeltnis = 1.5});
  final Map<String, dynamic> modell;
  final bool kameraHalten;
  final double seitenverhaeltnis;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb) {
      return _AppModell(modell: modell, kameraHalten: kameraHalten, seitenverhaeltnis: seitenverhaeltnis);
    }
    return AspectRatio(
      aspectRatio: seitenverhaeltnis,
      child: Semantics(
        label: tr('modell_3d'),
        child: WebModell(url: '$apiBasis/ansicht?sprache=$sprache', modell: modell, kameraHalten: kameraHalten),
      ),
    );
  }
}

class _AppModell extends StatefulWidget {
  const _AppModell({required this.modell, this.kameraHalten = false, this.seitenverhaeltnis = 1.5});

  /// Teile als Quader wie in der Antwort von /api/v1/bauplan/berechnen (Feld "modell").
  final Map<String, dynamic> modell;

  /// Beim Strecken: Kamera nicht mitzoomen, damit man das Möbel wachsen sieht.
  final bool kameraHalten;
  final double seitenverhaeltnis;

  @override
  State<_AppModell> createState() => _ModellAnsichtState();
}

class _ModellAnsichtState extends State<_AppModell> {
  late final WebViewController _web;
  bool _bereit = false;

  @override
  void initState() {
    super.initState();
    _web = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFEEF0F2))
      ..addJavaScriptChannel('Bereit', onMessageReceived: (_) {
        _bereit = true;
        _senden();
      })
      ..loadRequest(Uri.parse('$apiBasis/ansicht?sprache=$sprache'));
  }

  @override
  void didUpdateWidget(_AppModell alt) {
    super.didUpdateWidget(alt);
    if (!identical(alt.modell, widget.modell)) _senden();
  }

  void _senden() {
    if (!_bereit) return;
    _web.runJavaScript('zeigen(${jsonEncode(widget.modell)}, ${widget.kameraHalten})');
  }

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: widget.seitenverhaeltnis,
      child: Semantics(
        label: tr('modell_3d'),
        child: WebViewWidget(
          controller: _web,
          // Ziehen dreht das Modell, statt die Seite zu scrollen
          gestureRecognizers: {Factory<OneSequenceGestureRecognizer>(() => EagerGestureRecognizer())},
        ),
      ),
    );
  }
}


/// AR: das Möbel in echter Größe im Zimmer.
/// iPhone: AR Quick Look öffnet die USDZ-Datei vom Server. Android: Googles Scene Viewer öffnet die GLB-Datei
/// (braucht die Google-App bzw. ARCore und einen Server im Netz – mit dem lokalen Server geht es nicht).
/// [planHolen] liefert die Antwort von „berechnen“ (z. B. erst nach dem Neurechnen mit neuen Maßen) oder null.
class ArKnopf extends StatelessWidget {
  const ArKnopf({super.key, required this.planHolen});
  final Future<Map<String, dynamic>?> Function() planHolen;

  static bool get _iPhone => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;
  static bool get _android => !kIsWeb && defaultTargetPlatform == TargetPlatform.android;
  static bool get moeglich => _iPhone || _android;

  Future<void> _oeffnen(BuildContext context) async {
    final hinweise = ScaffoldMessenger.of(context);
    try {
      final plan = await planHolen();
      if (plan == null) return;
      final Uri url;
      if (_iPhone) {
        final usdz = plan['modell_usdz'] as String?;
        if (usdz == null) return;
        // Größe festhalten: Es soll in echter Größe im Zimmer stehen, nicht per Fingerzug skaliert werden
        url = Uri.parse('$apiBasis$usdz#allowsContentScaling=0');
      } else {
        final glb = plan['modell_glb'] as String?;
        if (glb == null) return;
        url = Uri.https('arvr.google.com', '/scene-viewer/1.0', {
          'file': '$apiBasis$glb',
          'mode': 'ar_preferred', // AR, sonst 3D
          'resizable': 'false', // echte Größe
          'title': 'Parawerk',
        });
      }
      final modus = _iPhone ? LaunchMode.inAppBrowserView : LaunchMode.externalApplication;
      if (!await launchUrl(url, mode: modus) && !await launchUrl(url, mode: LaunchMode.externalApplication)) {
        hinweise.showSnackBar(SnackBar(content: Text(tr('ar_geht_nicht'))));
      }
    } catch (_) {
      hinweise.showSnackBar(SnackBar(content: Text(tr('ar_geht_nicht'))));
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!moeglich) return const SizedBox.shrink();
    return FilledButton.tonalIcon(
      onPressed: () => _oeffnen(context),
      icon: const Icon(Icons.view_in_ar),
      label: Text(tr('im_raum')),
      style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
    );
  }
}
