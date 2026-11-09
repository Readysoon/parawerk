// Meine Projekte: die Baupläne, die nach der Anmeldung gespeichert wurden (je Entwurf eins).
// Antippen öffnet den Bauplan (wird mit den gespeicherten Maßen neu gerechnet), der Mülleimer löscht.
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api.dart';
import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'bauplan.dart';

class ProjekteSeite extends StatefulWidget {
  const ProjekteSeite({super.key, required this.api});
  final Api api;

  @override
  State<ProjekteSeite> createState() => _ProjekteSeiteState();
}

class _ProjekteSeiteState extends State<ProjekteSeite> {
  late Future<List<Projekt>> _liste = widget.api.projekte();

  Future<void> _neuLaden() async {
    final f = widget.api.projekte();
    setState(() => _liste = f);
    await f;
  }

  Future<void> _oeffnen(Projekt p) async {
    final api = widget.api;
    final geladen = await mitWarten(context, tr('st_rechnen'), () async {
      final j = await api.projektOeffnen(p.id);
      final bereich = [for (final v in j['bereich'] as List) (v as num).round()];
      final graph = j['graph'] as Map<String, dynamic>;
      final e = j['entwurf'] as Map<String, dynamic>;
      final entwurf = Entwurf(e['id'] as String, e['url'] as String);
      final plan = await api.berechnen(graph, bereich, entwurfId: entwurf.id);
      return (bereich, graph, entwurf, plan);
    });
    if (geladen == null || !mounted) return;
    final (bereich, graph, entwurf, plan) = geladen;
    // eigene Sitzung ohne Foto: Bauplan, Größe ändern, PDF gehen mit Entwurf und Bereich
    final s = Sitzung(api: api, foto: Uint8List(0), maske: Uint8List(0), bildBreite: 0, bildHoehe: 0)
      ..bereich = bereich
      ..anmeldungErledigt = true
      ..bezahlt.add(entwurf.id);
    await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => BauplanSeite(sitzung: s, entwurf: entwurf, graph: graph, plan: plan, maengel: const [])));
    if (mounted) _neuLaden();
  }

  Future<void> _loeschen(Projekt p) async {
    final ja = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(tr('projekt_loeschen')),
        content: Text(tr('projekt_loeschen_frage', {'name': p.name})),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: Text(tr('abbrechen'))),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: Text(tr('loeschen'))),
        ],
      ),
    );
    if (ja != true || !mounted) return;
    final hinweise = ScaffoldMessenger.of(context);
    try {
      await widget.api.projektLoeschen(p.id);
      await _neuLaden();
    } catch (e) {
      hinweise.showSnackBar(SnackBar(content: Text(fehlerText(e))));
    }
  }

  String _datum(DateTime? d) => d == null ? '' : '${d.day}.${d.month}.${d.year}';

  @override
  Widget build(BuildContext context) {
    final stil = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(title: Text(tr('meine_projekte'))),
      body: RefreshIndicator(
        onRefresh: _neuLaden,
        child: FutureBuilder<List<Projekt>>(
          future: _liste,
          builder: (context, snap) {
            if (snap.connectionState != ConnectionState.done) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snap.hasError) {
              return ListView(padding: const EdgeInsets.all(24), children: [Text(fehlerText(snap.error!))]);
            }
            final liste = snap.data ?? const <Projekt>[];
            if (liste.isEmpty) {
              return ListView(padding: const EdgeInsets.all(24), children: [Text(tr('projekte_leer'))]);
            }
            return ListView.separated(
              padding: const EdgeInsets.symmetric(vertical: 8),
              itemCount: liste.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final p = liste[i];
                final bild = p.vollBildUrl;
                return ListTile(
                  onTap: () => _oeffnen(p),
                  leading: ClipRRect(
                    borderRadius: BorderRadius.circular(6),
                    child: SizedBox(
                      width: 64,
                      height: 64,
                      child: bild == null
                          ? const ColoredBox(color: Colors.black12, child: Icon(Icons.chair_outlined))
                          : Image.network(bild, fit: BoxFit.cover,
                              errorBuilder: (_, __, ___) => const ColoredBox(color: Colors.black12)),
                    ),
                  ),
                  title: Text(p.name, maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text(
                    [if (p.masse.length == 3) '${p.masse.join(' × ')} mm', _datum(p.geaendert)]
                        .where((x) => x.isNotEmpty)
                        .join(' · '),
                    style: stil.bodySmall,
                  ),
                  trailing: IconButton(
                    tooltip: tr('projekt_loeschen'),
                    icon: const Icon(Icons.delete_outline),
                    onPressed: () => _loeschen(p),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
