// Kleine Hilfen für alle Seiten: Wartedialog bei langen Aufrufen, Fehler anzeigen.
import 'package:flutter/material.dart';

import 'texte.dart';

/// Zeigt einen Wartedialog mit [text], solange [arbeit] läuft. Fehler erscheinen als Hinweis unten;
/// dann ist das Ergebnis null.
Future<T?> mitWarten<T>(BuildContext context, String text, Future<T> Function() arbeit) async {
  final navigator = Navigator.of(context, rootNavigator: true);
  final hinweise = ScaffoldMessenger.of(context);
  showDialog<void>(
    context: context,
    barrierDismissible: false,
    builder: (_) => PopScope(
      canPop: false,
      child: AlertDialog(
        content: Row(children: [
          const CircularProgressIndicator(),
          const SizedBox(width: 20),
          Expanded(child: Text(text)),
        ]),
      ),
    ),
  );
  try {
    return await arbeit();
  } catch (e) {
    hinweise.showSnackBar(SnackBar(content: Text('$e'), duration: const Duration(seconds: 6)));
    return null;
  } finally {
    navigator.pop();
  }
}

/// Überschrift eines Abschnitts.
class Abschnitt extends StatelessWidget {
  const Abschnitt(this.text, {super.key});
  final String text;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 8),
        child: Text(text.toUpperCase(),
            style: Theme.of(context).textTheme.labelLarge?.copyWith(letterSpacing: 1.2, color: Colors.black54)),
      );
}

/// Grauer Hinweis zum Gratis-Rest, z. B. „Noch 1 Gratis-Runde“.
class FreiHinweis extends StatelessWidget {
  const FreiHinweis(this.text, {super.key});
  final String? text;

  @override
  Widget build(BuildContext context) => text == null
      ? const SizedBox.shrink()
      : Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text(text!, style: const TextStyle(color: Colors.black54, fontSize: 13)),
        );
}

String fehlerText(Object e) => '${tr('fehler')}: $e';
