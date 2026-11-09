// Breite, Tiefe und Höhe in mm eintippen (statt Regler). Übernommen wird beim Bestätigen (Enter/Fertig) oder
// wenn man das Feld verlässt; Werte außerhalb von 250–4000 mm werden auf die Grenze gesetzt.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'texte.dart';

const int massMin = 250, massMax = 4000;

class MassFelder extends StatefulWidget {
  const MassFelder({super.key, required this.werte, required this.geaendert, this.gesperrt = false});

  /// Breite, Tiefe, Höhe in mm.
  final List<int> werte;
  final void Function(List<int> neu) geaendert;
  final bool gesperrt;

  @override
  State<MassFelder> createState() => _MassFelderState();
}

class _MassFelderState extends State<MassFelder> {
  late final List<TextEditingController> _feld = [for (final v in widget.werte) TextEditingController(text: '$v')];
  late final List<FocusNode> _fokus = [
    for (var i = 0; i < 3; i++) FocusNode()..addListener(() => _verlassen(i)),
  ];

  @override
  void didUpdateWidget(MassFelder alt) {
    super.didUpdateWidget(alt);
    // neue Werte von außen (z. B. nach dem Neurechnen) übernehmen, aber nicht ins gerade bearbeitete Feld schreiben
    for (var i = 0; i < 3; i++) {
      if (!_fokus[i].hasFocus && _feld[i].text != '${widget.werte[i]}') _feld[i].text = '${widget.werte[i]}';
    }
  }

  @override
  void dispose() {
    for (final f in _feld) {
      f.dispose();
    }
    for (final f in _fokus) {
      f.dispose();
    }
    super.dispose();
  }

  void _verlassen(int i) {
    if (!_fokus[i].hasFocus) _uebernehmen();
  }

  void _uebernehmen() {
    final neu = [
      for (var i = 0; i < 3; i++) (int.tryParse(_feld[i].text.trim()) ?? widget.werte[i]).clamp(massMin, massMax),
    ];
    for (var i = 0; i < 3; i++) {
      if (_feld[i].text != '${neu[i]}') _feld[i].text = '${neu[i]}';
    }
    if ([for (var i = 0; i < 3; i++) neu[i] != widget.werte[i]].contains(true)) widget.geaendert(neu);
  }

  @override
  Widget build(BuildContext context) {
    return Row(children: [
      for (final (i, key) in const ['breite', 'tiefe', 'hoehe'].indexed) ...[
        if (i > 0) const SizedBox(width: 8),
        Expanded(
          child: TextField(
            controller: _feld[i],
            focusNode: _fokus[i],
            enabled: !widget.gesperrt,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly, LengthLimitingTextInputFormatter(4)],
            textInputAction: i < 2 ? TextInputAction.next : TextInputAction.done,
            onSubmitted: (_) => _uebernehmen(),
            style: const TextStyle(fontFeatures: [FontFeature.tabularFigures()]),
            decoration: InputDecoration(
              labelText: tr(key),
              suffixText: 'mm',
              border: const OutlineInputBorder(),
              isDense: true,
            ),
          ),
        ),
      ],
    ]);
  }
}
