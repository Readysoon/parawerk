// Bauplan: 3D-Modell, Prüfung, Einkaufsliste, Montage, Zuschnitt. Per Text anpassen.
// Alle Texte des Bauplans kommen fertig übersetzt vom Server.
import 'package:flutter/material.dart';
import 'package:model_viewer_plus/model_viewer_plus.dart';

import '../api.dart';
import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';

class BauplanSeite extends StatefulWidget {
  const BauplanSeite({
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
  final Map<String, dynamic> plan; // Antwort von /api/v1/bauplan/berechnen
  final List<String> maengel; // von der Selbstkontrolle korrigiert

  @override
  State<BauplanSeite> createState() => _BauplanSeiteState();
}

class _BauplanSeiteState extends State<BauplanSeite> {
  late Map<String, dynamic> _graph = widget.graph;
  late Map<String, dynamic> _plan = widget.plan;
  final _wunsch = TextEditingController();

  @override
  void dispose() {
    _wunsch.dispose();
    super.dispose();
  }

  Future<void> _anpassen() async {
    final text = _wunsch.text.trim();
    if (text.isEmpty) return;
    final s = widget.sitzung;
    final neu = await mitWarten(context, tr('st_anpassen'), () async {
      final graph = await s.api.anpassen(_graph, text);
      final plan = await s.api.berechnen(graph, s.bereich);
      return (graph: graph, plan: plan);
    });
    if (neu == null || !mounted) return;
    setState(() {
      _graph = neu.graph;
      _plan = neu.plan;
      _wunsch.clear();
    });
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(tr('geaendert'))));
  }

  List<Map<String, dynamic>> _liste(Map<String, dynamic> b, String key) =>
      ((b[key] as List?) ?? const []).cast<Map<String, dynamic>>();

  @override
  Widget build(BuildContext context) {
    final b = _plan['bauplan'] as Map<String, dynamic>;
    final offen = (_plan['offene_punkte'] as num?)?.toInt() ?? 0;
    final glb = _plan['modell_glb'] as String?;
    final stil = Theme.of(context).textTheme;

    return Scaffold(
      appBar: AppBar(title: Text('${tr('bauplan_titel')}: ${_plan['name']}')),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.all(16), children: [
          // Status
          Align(
            alignment: Alignment.centerLeft,
            child: Chip(
              avatar: Icon(offen == 0 ? Icons.check_circle : Icons.warning_amber,
                  color: offen == 0 ? const Color(0xFF2F7D4F) : const Color(0xFFA15C00)),
              label: Text(offen == 0 ? tr('ok') : tr('punkte', {'n': offen})),
            ),
          ),
          const SizedBox(height: 8),
          // Entwurf und 3D-Modell
          ClipRRect(borderRadius: BorderRadius.circular(6), child: Image.network(widget.entwurf.vollUrl)),
          if (glb != null) ...[
            const SizedBox(height: 12),
            SizedBox(
              height: 300,
              child: ModelViewer(
                key: ValueKey(glb), // neues Modell nach dem Anpassen
                src: '$apiBasis$glb',
                alt: tr('modell_3d'),
                cameraControls: true,
                autoRotate: true,
                backgroundColor: const Color(0xFFEEF0F2),
              ),
            ),
            Text(tr('modell_3d'), style: stil.bodySmall),
          ],

          if (widget.maengel.isNotEmpty) ...[
            Abschnitt(tr('selbstkontrolle')),
            Text(tr('selbstkontrolle_text')),
            for (final m in widget.maengel) Text('• $m'),
          ],

          Abschnitt(tr('ergebnis')),
          _Zeile(tr('aussenmass'), '${b['aussenmass']} mm'),
          _Zeile(tr('einzelteile'), '${b['anzahl_teile']}'),
          _Zeile(tr('ergaenzt'), '${b['anzahl_ergaenzt']}'),

          Abschnitt(tr('pruefung')),
          for (final p in _liste(b, 'pruefungen'))
            ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                p['klasse'] == 'ok' ? Icons.check : p['klasse'] == 'no' ? Icons.warning_amber : Icons.info_outline,
                color: p['klasse'] == 'ok' ? const Color(0xFF2F7D4F) : p['klasse'] == 'no' ? const Color(0xFFA15C00) : null,
              ),
              title: Text('${p['text']}'),
            ),

          Abschnitt(tr('einkauf')),
          for (final l in _liste(b, 'einkauf')) _Zeile('${l['text']}', '${l['n']}×'),
          for (final l in _liste(b, 'beschlaege')) _Zeile('${l['text']} ${tr('reserve')}', '${l['n']}'),

          Abschnitt(tr('montage')),
          for (final (i, m) in _liste(b, 'montage').indexed)
            Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Text('${i + 1}. ${m['t']} (${tr('teile', {'n': m['n']})})'),
            ),

          Abschnitt(tr('zuschnitt')),
          for (final g in _liste(b, 'zuschnitt')) ...[
            Padding(
              padding: const EdgeInsets.only(top: 6, bottom: 2),
              child: Text('${g['label']}', style: const TextStyle(fontWeight: FontWeight.w600)),
            ),
            if (g['art'] == 'stab')
              ...[for (final st in (g['stangen'] as List).cast<Map<String, dynamic>>()) _Stange(st)]
            else
              Text('${(g['platten'] as List).length}×'),
          ],

          Abschnitt(tr('anpassen')),
          TextField(
            controller: _wunsch,
            maxLength: 500,
            decoration: InputDecoration(hintText: tr('anpassen_platzhalter'), border: const OutlineInputBorder()),
            onSubmitted: (_) => _anpassen(),
          ),
          Align(alignment: Alignment.centerLeft, child: OutlinedButton(onPressed: _anpassen, child: Text(tr('anpassen')))),
          const SizedBox(height: 24),
        ]),
      ),
    );
  }
}

class _Zeile extends StatelessWidget {
  const _Zeile(this.links, this.rechts);
  final String links;
  final String rechts;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Expanded(child: Text(links)),
          const SizedBox(width: 12),
          Text(rechts),
        ]),
      );
}

/// Eine Stange mit ihren Zuschnitten als Balken.
class _Stange extends StatelessWidget {
  const _Stange(this.s);
  final Map<String, dynamic> s;

  @override
  Widget build(BuildContext context) {
    final laenge = (s['laenge'] as num).toDouble();
    final stuecke = (s['stuecke'] as List).cast<Map<String, dynamic>>();
    final meter = (laenge / 1000).toStringAsFixed(2);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Row(children: [
          Expanded(
            child: Text(tr('stange', {'n': s['anzahl'], 'm': sprache == 'de' ? meter.replaceAll('.', ',') : meter}),
                style: const TextStyle(fontSize: 12, color: Colors.black54)),
          ),
          Text(tr('rest', {'n': s['rest']}), style: const TextStyle(fontSize: 12, color: Colors.black54)),
        ]),
        const SizedBox(height: 2),
        LayoutBuilder(builder: (context, groesse) {
          return Container(
            height: 22,
            decoration: BoxDecoration(border: Border.all(color: const Color(0xFFD5DAE0)), color: const Color(0xFFEEF0F2)),
            child: Row(children: [
              for (final p in stuecke)
                Container(
                  width: (groesse.maxWidth - 2) * (p['len'] as num) / laenge,
                  decoration: BoxDecoration(
                    color: p['ergaenzt'] == true ? const Color(0xFFC2410C) : const Color(0xFFD8C2A0),
                    border: const Border(right: BorderSide(color: Colors.white, width: 2)),
                  ),
                  alignment: Alignment.center,
                  child: Text('${p['len']}', style: const TextStyle(fontSize: 10), overflow: TextOverflow.clip, maxLines: 1),
                ),
            ]),
          );
        }),
      ]),
    );
  }
}
