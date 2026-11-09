// 3D-Modell anzeigen: derselbe Viewer wie auf der Website (Seite /ansicht), eingebettet als Webfenster.
// Die App schickt nur die Teile als Daten hinein, darum kann das Modell beim Strecken live mitwachsen.
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'api.dart';
import 'modell_web_ersatz.dart' if (dart.library.js_interop) 'modell_web.dart';
import 'texte.dart';

/// Im Browser ein iframe, sonst ein Webfenster (webview_flutter gibt es im Browser nicht).
class ModellAnsicht extends StatelessWidget {
  const ModellAnsicht(
      {super.key, required this.modell, this.kameraHalten = false, this.verzerren = false, this.seitenverhaeltnis = 1.5});
  final Map<String, dynamic> modell;
  final bool kameraHalten;

  /// Gitterpunkte zum freien Verzerren zeigen (nur Vorschau).
  final bool verzerren;
  final double seitenverhaeltnis;

  @override
  Widget build(BuildContext context) {
    if (!kIsWeb) {
      return _AppModell(
          modell: modell, kameraHalten: kameraHalten, verzerren: verzerren, seitenverhaeltnis: seitenverhaeltnis);
    }
    return AspectRatio(
      aspectRatio: seitenverhaeltnis,
      child: Semantics(
        label: tr('modell_3d'),
        child: WebModell(
            url: '$apiBasis/ansicht?sprache=$sprache', modell: modell, kameraHalten: kameraHalten, verzerren: verzerren),
      ),
    );
  }
}

class _AppModell extends StatefulWidget {
  const _AppModell(
      {required this.modell, this.kameraHalten = false, this.verzerren = false, this.seitenverhaeltnis = 1.5});

  /// Teile als Quader wie in der Antwort von /api/v1/bauplan/berechnen (Feld "modell").
  final Map<String, dynamic> modell;

  /// Beim Strecken: Kamera nicht mitzoomen, damit man das Möbel wachsen sieht.
  final bool kameraHalten;
  final bool verzerren;
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
    if (!identical(alt.modell, widget.modell) || alt.verzerren != widget.verzerren) _senden();
  }

  void _senden() {
    if (!_bereit) return;
    _web.runJavaScript('zeigen(${jsonEncode(widget.modell)}, ${widget.kameraHalten}, ${widget.verzerren})');
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
