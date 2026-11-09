// Ersatz für modell_web.dart auf iPhone und Android (dort gibt es kein dart:js_interop); wird nie angezeigt.
import 'package:flutter/material.dart';

class WebModell extends StatelessWidget {
  const WebModell(
      {super.key, required this.url, required this.modell, required this.kameraHalten, this.verzerren = false});
  final String url;
  final Map<String, dynamic> modell;
  final bool kameraHalten;
  final bool verzerren;

  @override
  Widget build(BuildContext context) => const SizedBox.shrink();
}
