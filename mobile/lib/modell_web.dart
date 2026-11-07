// 3D-Modell, wenn die App im Browser läuft (flutter run -d chrome): die Seite /ansicht steckt in einem iframe,
// das Modell geht per postMessage hinein (auf iPhone und Android übernimmt das webview_flutter).
import 'dart:js_interop';

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

class WebModell extends StatefulWidget {
  const WebModell({super.key, required this.url, required this.modell, required this.kameraHalten});
  final String url;
  final Map<String, dynamic> modell;
  final bool kameraHalten;

  @override
  State<WebModell> createState() => _WebModellState();
}

class _WebModellState extends State<WebModell> {
  web.HTMLIFrameElement? _frame;
  bool _bereit = false;
  late final JSFunction _horcher;
  late final String _herkunft = Uri.parse(widget.url).origin;

  @override
  void initState() {
    super.initState();
    _horcher = ((web.MessageEvent ev) {
      if (ev.origin != _herkunft) return;
      final d = ev.data.dartify();
      if (d is Map && d['parawerk'] == 'bereit') {
        _bereit = true;
        _senden();
      }
    }).toJS;
    web.window.addEventListener('message', _horcher);
  }

  @override
  void didUpdateWidget(WebModell alt) {
    super.didUpdateWidget(alt);
    if (!identical(alt.modell, widget.modell)) _senden();
  }

  void _senden() {
    final ziel = _frame?.contentWindow;
    if (!_bereit || ziel == null) return;
    ziel.postMessage({'parawerk': 'zeigen', 'modell': widget.modell, 'kameraHalten': widget.kameraHalten}.jsify(),
        _herkunft.toJS);
  }

  @override
  void dispose() {
    web.window.removeEventListener('message', _horcher);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return HtmlElementView.fromTagName(
      tagName: 'iframe',
      onElementCreated: (Object el) {
        final f = el as web.HTMLIFrameElement;
        f.src = widget.url;
        f.style.border = 'none';
        f.style.width = '100%';
        f.style.height = '100%';
        _frame = f;
      },
    );
  }
}
