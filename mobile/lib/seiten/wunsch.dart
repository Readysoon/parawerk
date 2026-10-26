// Wunsch und Maße eingeben, dann Entwürfe malen lassen.
import 'package:flutter/material.dart';

import '../api.dart';
import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'entwuerfe.dart';
import 'messen.dart';

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
  String? _messHinweis; // Ergebnis der Messung im Foto

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

  Future<void> _code() async {
    final eingabe = TextEditingController();
    final code = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(tr('code_frage')),
        content: TextField(
          controller: eingabe,
          autofocus: true,
          textCapitalization: TextCapitalization.characters,
          onSubmitted: (v) => Navigator.of(context).pop(v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(tr('abbrechen'))),
          FilledButton(onPressed: () => Navigator.of(context).pop(eingabe.text), child: Text(tr('code_los'))),
        ],
      ),
    );
    // eingabe nicht sofort freigeben: Der Dialog baut beim Ausblenden noch einmal auf
    if (code == null || code.trim().isEmpty || !mounted) return;
    final hinweise = ScaffoldMessenger.of(context);
    try {
      final k = await widget.sitzung.api.codeEinloesen(code.trim());
      if (mounted) setState(() => _frei = frei('frei_runden', k.runden));
      hinweise.showSnackBar(SnackBar(content: Text(tr('code_ok'))));
    } catch (e) {
      hinweise.showSnackBar(SnackBar(content: Text(fehlerText(e))));
    }
  }

  Future<void> _messen() async {
    final ergebnis = await Navigator.of(context).push<MassErgebnis>(
      MaterialPageRoute(builder: (_) => MessenSeite(sitzung: widget.sitzung)),
    );
    if (ergebnis == null || !mounted) return;
    setState(() {
      for (var i = 0; i < 3; i++) {
        final v = ergebnis.bereich[i];
        if (v != null) _masse[i].text = '$v';
      }
      _messHinweis = [tr('gemessen'), ...ergebnis.hinweise].join(' ');
    });
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
          Row(children: [
            Expanded(child: Abschnitt(tr('masse'))),
            TextButton.icon(onPressed: _messen, icon: const Icon(Icons.straighten), label: Text(tr('im_foto_messen'))),
          ]),
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
          if (_messHinweis != null)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Text(_messHinweis!, style: const TextStyle(color: Colors.black54, fontSize: 13)),
            ),
          const SizedBox(height: 24),
          FilledButton(
            onPressed: _entwerfen,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            child: Text(tr('entwerfen')),
          ),
          FreiHinweis(_frei),
          Align(alignment: Alignment.centerLeft, child: TextButton(onPressed: _code, child: Text(tr('code_frage')))),
        ]),
      ),
    );
  }
}
