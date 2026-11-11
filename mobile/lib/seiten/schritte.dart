// Die Schritte zwischen Entwurf und Bauplan:
//   1. Anmelden (vorerst nur Demo, ein Code überspringt den Schritt)
//   2. 3D-Modell ansehen, strecken und frei verzerren (die Vorschau rechnet die App selbst)
//   3. Bezahlen (vorerst nur Demo, ein Code schaltet frei)
// Danach kommt die Bauplan-Seite.
import 'package:flutter/material.dart';

import '../api.dart';
import '../hilfen.dart';
import '../mass_felder.dart';
import '../modell_ansicht.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'bauplan.dart';

/// Zeigt, in welchem der drei Schritte man gerade ist.
class _Schritte extends StatelessWidget {
  const _Schritte(this.aktuell);
  final int aktuell; // 0, 1 oder 2

  @override
  Widget build(BuildContext context) {
    final farbe = Theme.of(context).colorScheme.primary;
    final namen = [tr('schritt_anmelden'), tr('schritt_3d'), tr('schritt_bezahlen')];
    return Row(children: [
      for (final (i, n) in namen.indexed) ...[
        if (i > 0) Expanded(child: Divider(color: i <= aktuell ? farbe : Colors.black26, thickness: 2)),
        Column(mainAxisSize: MainAxisSize.min, children: [
          CircleAvatar(
            radius: 12,
            backgroundColor: i <= aktuell ? farbe : Colors.black12,
            child: i < aktuell
                ? const Icon(Icons.check, size: 14, color: Colors.white)
                : Text('${i + 1}', style: TextStyle(fontSize: 12, color: i <= aktuell ? Colors.white : Colors.black54)),
          ),
          const SizedBox(height: 4),
          Text(n, style: TextStyle(fontSize: 12, color: i == aktuell ? farbe : Colors.black54)),
        ]),
      ],
    ]);
  }
}

/// Code eingeben und einlösen; [einloesen] wirft bei falschem Code.
class _CodeFeld extends StatefulWidget {
  const _CodeFeld({required this.einloesen});
  final Future<void> Function(String code) einloesen;

  @override
  State<_CodeFeld> createState() => _CodeFeldState();
}

class _CodeFeldState extends State<_CodeFeld> {
  final _code = TextEditingController();
  bool _laeuft = false;
  String? _fehler;

  @override
  void dispose() {
    _code.dispose();
    super.dispose();
  }

  Future<void> _los() async {
    final code = _code.text.trim();
    if (code.isEmpty) return;
    setState(() {
      _laeuft = true;
      _fehler = null;
    });
    try {
      await widget.einloesen(code);
    } catch (e) {
      if (mounted) setState(() => _fehler = '$e');
    } finally {
      if (mounted) setState(() => _laeuft = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Row(children: [
        Expanded(
          child: TextField(
            controller: _code,
            textCapitalization: TextCapitalization.characters,
            decoration: InputDecoration(hintText: tr('code_frage'), border: const OutlineInputBorder(), isDense: true),
            onSubmitted: (_) => _los(),
          ),
        ),
        const SizedBox(width: 8),
        OutlinedButton(onPressed: _laeuft ? null : _los, child: Text(tr('code_los'))),
      ]),
      if (_laeuft) const Padding(padding: EdgeInsets.only(top: 8), child: LinearProgressIndicator()),
      if (_fehler != null)
        Padding(padding: const EdgeInsets.only(top: 6), child: Text(_fehler!, style: const TextStyle(color: Colors.red))),
    ]);
  }
}

/// Schritt 1: Anmelden. Ergebnis 'demo' (angemeldet, Projekte werden gespeichert) oder 'code' (ohne Anmeldung weiter).
class AnmeldeSchritt extends StatelessWidget {
  const AnmeldeSchritt({super.key, required this.sitzung});
  final Sitzung sitzung;

  @override
  Widget build(BuildContext context) {
    final stil = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(tr('schritt_anmelden'))),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          const _Schritte(0),
          const SizedBox(height: 24),
          Text(tr('konto_titel'), style: stil.titleLarge),
          const SizedBox(height: 8),
          Text(tr('anmelden_warum')),
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pop('demo'),
            icon: const Icon(Icons.science_outlined),
            label: Text(tr('demo_anmelden')),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 6),
          Text(tr('demo_anmelden_hinweis'), style: stil.bodySmall),
          const SizedBox(height: 24),
          Text(tr('code_ueberspringen'), style: stil.titleSmall),
          const SizedBox(height: 8),
          _CodeFeld(einloesen: (code) async {
            await sitzung.api.codeEinloesen(code);
            if (context.mounted) Navigator.of(context).pop('code');
          }),
        ]),
      ),
    );
  }
}

/// Modell gleichmäßig je Richtung strecken: Vorschau ohne Server (Bretter werden dabei mitgestreckt).
Map<String, dynamic> skaliert(Map<String, dynamic> modell, List<double> f) {
  List<double> s(List<dynamic> l) => [for (final (i, v) in l.indexed) (v as num).toDouble() * f[i]];
  Map<String, dynamic> teil(Map<dynamic, dynamic> t) =>
      {...t.cast<String, dynamic>(), 'min': s(t['min'] as List), 'max': s(t['max'] as List)};
  return {
    ...modell,
    'dims': s(modell['dims'] as List),
    'teile': [for (final t in modell['teile'] as List) teil(t as Map)],
    'polster': [for (final p in (modell['polster'] as List?) ?? const []) teil(p as Map)],
  };
}

/// Schritt 2: das Möbel in 3D. Breite, Tiefe und Höhe ziehen (Vorschau in der App), frei verzerren (nur Vorschau),
/// zerlegen und Teile antippen. „Weiter“ rechnet mit den neuen Maßen den echten Bauplan.
class ModellSchritt extends StatefulWidget {
  const ModellSchritt({
    super.key,
    required this.sitzung,
    required this.entwurf,
    required this.graph,
    required this.plan,
    this.maengel = const [],
  });
  final Sitzung sitzung;
  final Entwurf entwurf;
  final Map<String, dynamic> graph;
  final Map<String, dynamic> plan;
  final List<String> maengel;

  @override
  State<ModellSchritt> createState() => _ModellSchrittState();
}

class _ModellSchrittState extends State<ModellSchritt> {
  late final Map<String, dynamic> _modell = widget.plan['modell'] as Map<String, dynamic>;
  late final List<int> _design = [for (final v in _modell['dims'] as List) (v as num).round()];
  late List<double> _regler = [for (final v in _design) v.toDouble()];
  late Map<String, dynamic> _anzeige = _modell;
  bool _verzerren = false;

  bool get _geaendert => [for (final (i, v) in _regler.indexed) v.round() != _design[i]].contains(true);

  void _neueMasse(List<int> neu) {
    setState(() {
      _regler = [for (final v in neu) v.toDouble()];
      _anzeige = skaliert(_modell, [for (final (j, r) in _regler.indexed) r / _design[j]]);
    });
  }

  void _zurueck() => setState(() {
        _regler = [for (final v in _design) v.toDouble()];
        _anzeige = _modell;
      });

  Future<void> _weiter() async {
    final s = widget.sitzung;
    var graph = widget.graph, plan = widget.plan;
    if (_geaendert) {
      final g = {...widget.graph, 'ziel': [for (final v in _regler) v.round()]};
      final neu = await mitWarten(context, tr('st_rechnen'), () => s.berechnen(g, entwurfId: widget.entwurf.id));
      if (neu == null || !mounted) return;
      graph = g;
      plan = neu;
    }
    if (!mounted) return;
    final nav = Navigator.of(context);
    if (s.bezahlt.contains(widget.entwurf.id)) {
      nav.push(MaterialPageRoute<void>(
          builder: (_) =>
              BauplanSeite(sitzung: s, entwurf: widget.entwurf, graph: graph, plan: plan, maengel: widget.maengel)));
    } else {
      nav.push(MaterialPageRoute<void>(
          builder: (_) =>
              BezahlSchritt(sitzung: s, entwurf: widget.entwurf, graph: graph, plan: plan, maengel: widget.maengel)));
    }
  }

  @override
  Widget build(BuildContext context) {
    final stil = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(tr('schritt_3d_titel'))),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          const _Schritte(1),
          const SizedBox(height: 16),
          ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: ModellAnsicht(modell: _anzeige, kameraHalten: true, verzerren: _verzerren, seitenverhaeltnis: 1.0),
          ),
          const SizedBox(height: 6),
          Text(tr('schritt_3d_hinweis'), style: stil.bodySmall),
          Abschnitt(tr('groesse')),
          Text(tr('masse_eingeben'), style: stil.bodySmall),
          const SizedBox(height: 10),
          MassFelder(werte: [for (final v in _regler) v.round()], geaendert: _neueMasse),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(onPressed: _geaendert ? _zurueck : null, child: Text(tr('groesse_zurueck'))),
          ),
          Abschnitt(tr('verzerren')),
          SwitchListTile(
            contentPadding: EdgeInsets.zero,
            value: _verzerren,
            onChanged: (v) => setState(() => _verzerren = v),
            title: Text(tr('verzerren_an')),
            subtitle: Text(tr('verzerren_hinweis')),
          ),
          const SizedBox(height: 16),
          FilledButton(
            onPressed: _weiter,
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            child: Text(tr('weiter')),
          ),
          if (_geaendert)
            Padding(
              padding: const EdgeInsets.only(top: 6),
              child: Text(tr('weiter_neu_rechnen'), style: stil.bodySmall, textAlign: TextAlign.center),
            ),
        ]),
      ),
    );
  }
}

/// Schritt 3: Bezahlen (vorerst Demo) oder mit einem Code freischalten. Danach der Bauplan.
class BezahlSchritt extends StatelessWidget {
  const BezahlSchritt({
    super.key,
    required this.sitzung,
    required this.entwurf,
    required this.graph,
    required this.plan,
    this.maengel = const [],
  });
  final Sitzung sitzung;
  final Entwurf entwurf;
  final Map<String, dynamic> graph;
  final Map<String, dynamic> plan;
  final List<String> maengel;

  void _zumBauplan(BuildContext context, Map<String, dynamic> p) {
    sitzung.bezahlt.add(entwurf.id);
    Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
        builder: (_) => BauplanSeite(sitzung: sitzung, entwurf: entwurf, graph: graph, plan: p, maengel: maengel)));
  }

  @override
  Widget build(BuildContext context) {
    final stil = Theme.of(context).textTheme;
    final kopf = ((plan['bauplan'] as Map?)?['kopf'] as Map?) ?? const {};
    return Scaffold(
      appBar: AppBar(title: Text(tr('schritt_bezahlen'))),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          const _Schritte(2),
          const SizedBox(height: 24),
          Text(tr('frei_titel'), style: stil.titleLarge),
          const SizedBox(height: 8),
          for (final x in tr('frei_inhalt').split('|')) Padding(padding: const EdgeInsets.only(bottom: 2), child: Text('• $x')),
          if (kopf['preis_text'] != null) ...[
            const SizedBox(height: 8),
            Text('${tr('material')}: ${tr('ca')} ${kopf['preis_text']}', style: stil.bodySmall),
          ],
          const SizedBox(height: 20),
          FilledButton.icon(
            onPressed: () => _zumBauplan(context, plan),
            icon: const Icon(Icons.science_outlined),
            label: Text(tr('demo_bezahlen')),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(48)),
          ),
          const SizedBox(height: 6),
          Text(tr('demo_bezahlen_hinweis'), style: stil.bodySmall),
          const SizedBox(height: 24),
          Text(tr('code_freischalten'), style: stil.titleSmall),
          const SizedBox(height: 8),
          _CodeFeld(einloesen: (code) async {
            await sitzung.api.freischalten(code, graph, entwurfId: entwurf.id);
            // neu rechnen: jetzt vollständig freigeschaltet
            final neu = await sitzung.berechnen(graph, entwurfId: entwurf.id);
            if (context.mounted) _zumBauplan(context, neu);
          }),
        ]),
      ),
    );
  }
}
