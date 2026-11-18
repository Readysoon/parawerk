// Die 4 Entwürfe: einen auswählen, per Text ändern, Bauplan erstellen.
import 'package:flutter/material.dart';

import '../api.dart';
import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'schritte.dart';

class EntwuerfeSeite extends StatefulWidget {
  const EntwuerfeSeite({super.key, required this.sitzung, this.einzeln = false});
  final Sitzung sitzung;

  /// gleich nur den ersten Entwurf groß zeigen (altes Projekt weiter anpassen)
  final bool einzeln;

  @override
  State<EntwuerfeSeite> createState() => _EntwuerfeSeiteState();
}

class _EntwuerfeSeiteState extends State<EntwuerfeSeite> {
  late int _gewaehlt = widget.einzeln ? 0 : -1;
  final _aenderung = TextEditingController();
  final Map<int, List<Entwurf>> _verlauf = {}; // je Entwurf die Vorversionen, für „Rückgängig“
  late bool _einzeln = widget.einzeln; // nach dem Anpassen: nur der gewählte Entwurf, groß
  String? _freiNj;

  Sitzung get _s => widget.sitzung;

  @override
  void initState() {
    super.initState();
    _s.seiteAuf(routeEntwuerfe);
    _kontingent();
  }

  @override
  void dispose() {
    _s.seiteZu(routeEntwuerfe);
    _aenderung.dispose();
    super.dispose();
  }

  /// Schritt-Anzeige nach vorn: Für den gewählten Entwurf gibt es schon einen Plan → direkt hin, sonst neu erstellen.
  void _vor(int ziel) {
    if (_gewaehlt < 0) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(tr('erst_entwurf_waehlen'))));
      return;
    }
    if (_s.plan != null && _s.planEntwurf?.id == _s.entwuerfe[_gewaehlt].id) {
      schrittOeffnen(context, _s, ziel);
    } else {
      _bauplan();
    }
  }

  Future<void> _kontingent() async {
    try {
      final k = await _s.api.kontingent();
      if (mounted) setState(() => _freiNj = frei('frei_nj', k.nachjustieren));
    } catch (_) {}
  }

  Future<void> _nachjustieren() async {
    final text = _aenderung.text.trim();
    if (_gewaehlt < 0 || text.isEmpty) return;
    final i = _gewaehlt;
    final neu = await mitWarten(
      context,
      tr('st_nachjustieren'),
      () => _s.api.nachjustieren(
        fotoId: _s.fotoId!,
        maskeId: _s.maskeId!,
        entwurfId: _s.entwuerfe[i].id,
        wunsch: _s.wunsch,
        anpassung: text,
      ),
    );
    await _kontingent();
    if (neu == null || !mounted) return;
    setState(() {
      (_verlauf[i] ??= []).add(_s.entwuerfe[i]);
      _s.entwuerfe[i] = neu;
      _einzeln = true; // Text bleibt im Feld, damit man sieht, was geändert wurde, und weiter anpassen kann
    });
  }

  void _rueckgaengig() {
    final v = _verlauf[_gewaehlt];
    if (v == null || v.isEmpty) return;
    setState(() => _s.entwuerfe[_gewaehlt] = v.removeLast());
  }

  /// Bauplan: erst anmelden (einmal), dann rechnet der Server, dann 3D-Schritt und Bezahlen.
  Future<void> _bauplan() async {
    if (_gewaehlt < 0) return;
    final entwurf = _s.entwuerfe[_gewaehlt];
    if (!_s.anmeldungErledigt && !_s.api.projekteAn.value) {
      final wie = await Navigator.of(context).push<String>(MaterialPageRoute(
          settings: const RouteSettings(name: routeAnmelden), builder: (_) => AnmeldeSchritt(sitzung: _s)));
      if (wie == null || !mounted) return;
      _s.anmeldungErledigt = true;
    }
    final ergebnis = await mitWarten(context, tr('st_lesen'), () async {
      final gelesen = await _s.api.lesen(
        entwurfId: entwurf.id,
        maskeId: _s.maskeId!,
        bereich: _s.bereich,
        demoIndex: _s.demo ? _gewaehlt : null,
      );
      final plan = await _s.berechnen(gelesen.graph, entwurfId: entwurf.id);
      return (graph: gelesen.graph, plan: plan, maengel: gelesen.maengel);
    });
    if (ergebnis == null || !mounted) return;
    _s.merken(entwurf, ergebnis.graph, ergebnis.plan, ergebnis.maengel);
    Navigator.of(context).push(MaterialPageRoute<void>(
      settings: const RouteSettings(name: routeModell),
      builder: (_) =>
          ModellSchritt(sitzung: _s, entwurf: entwurf, graph: ergebnis.graph, plan: ergebnis.plan, maengel: ergebnis.maengel),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final hatVerlauf = (_verlauf[_gewaehlt] ?? const []).isNotEmpty;
    return Scaffold(
      appBar: AppBar(
        title: Text(tr('entwuerfe_titel')),
        // weiter zum nächsten Schritt (3D); neue Entwürfe gibt es ohnehin nur einmal am Tag
        actions: [IconButton(tooltip: tr('schritt_3d'), onPressed: () => _vor(1), icon: const Icon(Icons.chevron_right, size: 32))],
      ),
      body: SafeArea(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          // Schritt-Anzeige bleibt oben stehen
          Padding(padding: const EdgeInsets.fromLTRB(16, 12, 16, 8), child: Schritte(0, sitzung: _s, vor: _vor)),
          const Divider(height: 1),
          Expanded(
              child: ListView(padding: const EdgeInsets.all(12), children: [
          if (_einzeln && _gewaehlt >= 0) ...[
            // nach dem Anpassen: nur dieses Bild, groß
            ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Image.network(_s.entwuerfe[_gewaehlt].vollUrl, fit: BoxFit.contain),
            ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => setState(() => _einzeln = false),
                icon: const Icon(Icons.grid_view),
                label: Text(tr('alle_entwuerfe')),
              ),
            ),
          ] else ...[
          Text(tr('entwurf_hinweis')),
          const SizedBox(height: 8),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            mainAxisSpacing: 8,
            crossAxisSpacing: 8,
            childAspectRatio: 0.8,
            children: [
              for (final (i, e) in _s.entwuerfe.indexed)
                _Karte(
                  entwurf: e,
                  titel: tr('entwurf', {'n': i + 1}),
                  gewaehlt: i == _gewaehlt,
                  onTap: () => setState(() {
                    if (_gewaehlt != i) _aenderung.clear(); // anderer Entwurf: Anpassungstext gehört zum alten
                    _gewaehlt = i;
                  }),
                ),
            ],
          ),
          ],
          if (_gewaehlt >= 0) ...[
            // Hauptweg: Entwurf passt → gleich den Bauplan. Ändern ist nur eine Option darunter.
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _bauplan,
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
              child: Text(tr('bauplan_erstellen')),
            ),
            const SizedBox(height: 8),
            ExpansionTile(
              key: ValueKey(_einzeln), // nach dem Anpassen aufgeklappt
              title: Text(tr('nachjustieren')),
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: 8),
              initiallyExpanded: hatVerlauf || _einzeln,
              children: [
                TextField(
                  controller: _aenderung,
                  maxLength: 500,
                  decoration: InputDecoration(hintText: tr('nachjustieren_platzhalter'), border: const OutlineInputBorder()),
                  onSubmitted: (_) => _nachjustieren(),
                ),
                Row(children: [
                  OutlinedButton(onPressed: _nachjustieren, child: Text(tr('aendern'))),
                  const SizedBox(width: 8),
                  if (hatVerlauf) IconButton(onPressed: _rueckgaengig, icon: const Icon(Icons.undo)),
                ]),
                Align(alignment: Alignment.centerLeft, child: FreiHinweis(_freiNj)),
              ],
            ),
          ],
        ])),
        ]),
      ),
    );
  }
}

class _Karte extends StatelessWidget {
  const _Karte({required this.entwurf, required this.titel, required this.gewaehlt, required this.onTap});
  final Entwurf entwurf;
  final String titel;
  final bool gewaehlt;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.white,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(6),
        side: BorderSide(color: gewaehlt ? const Color(0xFFE8B400) : const Color(0xFFD5DAE0), width: gewaehlt ? 3 : 1),
      ),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: onTap,
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Expanded(
            child: Image.network(
              entwurf.vollUrl,
              fit: BoxFit.cover,
              loadingBuilder: (context, kind, fortschritt) =>
                  fortschritt == null ? kind : const Center(child: CircularProgressIndicator()),
              errorBuilder: (context, _, __) => const Center(child: Icon(Icons.broken_image)),
            ),
          ),
          Padding(padding: const EdgeInsets.all(6), child: Text(titel)),
        ]),
      ),
    );
  }
}
