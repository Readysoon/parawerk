// 3D-Modell anzeigen: derselbe Viewer wie auf der Website (Seite /ansicht), eingebettet als Webfenster.
// Die App schickt nur die Teile als Daten hinein, darum kann das Modell beim Strecken live mitwachsen.
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

import 'api.dart';
import 'texte.dart';

class ModellAnsicht extends StatefulWidget {
  const ModellAnsicht({super.key, required this.modell, this.kameraHalten = false});

  /// Teile als Quader wie in der Antwort von /api/v1/bauplan/berechnen (Feld "modell").
  final Map<String, dynamic> modell;

  /// Beim Strecken: Kamera nicht mitzoomen, damit man das Möbel wachsen sieht.
  final bool kameraHalten;

  @override
  State<ModellAnsicht> createState() => _ModellAnsichtState();
}

class _ModellAnsichtState extends State<ModellAnsicht> {
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
  void didUpdateWidget(ModellAnsicht alt) {
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
      aspectRatio: 1.5,
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
