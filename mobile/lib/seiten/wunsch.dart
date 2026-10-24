// Wunsch und Maße eingeben, dann Entwürfe malen lassen.
import 'package:flutter/material.dart';

import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'entwuerfe.dart';

class WunschSeite extends StatefulWidget {
  const WunschSeite({super.key, required this.sitzung});
  final Sitzung sitzung;

  @override
  State<WunschSeite> createState() => _WunschSeiteState();
}

class _WunschSeiteState extends State<WunschSeite> {
  late final _wunsch = TextEditingController(text: widget.sitzung.wunsch);
  late final _masse = [for (final v in widget.sitzung.bereich) TextEditingController(text: '$v')];
  String? _frei;

  static const _vorschlaege = {
    'de': ['Daybed aus Latten mit Polstern', 'Regal bis unter die Decke', 'Sitzbank mit Stauraum', 'niedriges Sideboard'],
    'en': ['Daybed made of battens with cushions', 'Shelf up to the ceiling', 'Bench with storage', 'Low sideboard'],
  };

  @override
  void initState() {
    super.initState();
    _kontingent();
  }

  @override
  void dispose() {
    _wunsch.dispose();
    for (final c in _masse) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _kontingent() async {
    try {
      final k = await widget.sitzung.api.kontingent();
      if (mounted) setState(() => _frei = frei('frei_runden', k.runden));
    } catch (_) {
      // nur ein Hinweis
    }
  }

  Future<void> _entwerfen() async {
    final s = widget.sitzung;
    s.wunsch = _wunsch.text.trim();
    s.bereich = [for (var i = 0; i < 3; i++) int.tryParse(_masse[i].text) ?? s.bereich[i]];
    final ok = await mitWarten(context, tr('st_entwerfen'), () async {
      await s.entwerfen();
      return true;
    });
    await _kontingent();
    if (ok == true && mounted) {
      Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => EntwuerfeSeite(sitzung: s)));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(tr('wunsch'))),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          TextField(
            controller: _wunsch,
            minLines: 2,
            maxLines: 4,
            maxLength: 500,
            decoration: InputDecoration(hintText: tr('wunsch_platzhalter'), border: const OutlineInputBorder()),
          ),
          Wrap(spacing: 8, runSpacing: 4, children: [
            for (final v in _vorschlaege[sprache] ?? _vorschlaege['en']!)
              ActionChip(label: Text(v), onPressed: () => setState(() => _wunsch.text = v)),
          ]),
          Abschnitt(tr('masse')),
          Row(children: [
            for (final (i, key) in const ['breite', 'tiefe', 'hoehe'].indexed) ...[
              if (i > 0) const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: _masse[i],
                  keyboardType: TextInputType.number,
                  decoration: InputDecoration(labelText: tr(key), border: const OutlineInputBorder()),
                ),
              ),
            ],
          ]),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _entwerfen,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            child: Text(tr('entwerfen')),
          ),
          FreiHinweis(_frei),
        ]),
      ),
    );
  }
}
