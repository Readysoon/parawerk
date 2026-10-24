// Bereich markieren: mit dem Finger über die Stelle malen, an der das Möbel stehen soll.
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../api.dart';
import '../malflaeche.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'wunsch.dart';

class MarkierenSeite extends StatefulWidget {
  const MarkierenSeite({super.key, required this.api, required this.foto, required this.bildBreite, required this.bildHoehe});

  final Api api;
  final Uint8List foto;
  final int bildBreite;
  final int bildHoehe;

  @override
  State<MarkierenSeite> createState() => _MarkierenSeiteState();
}

class _MarkierenSeiteState extends State<MarkierenSeite> {
  final _mal = MalSteuerung();

  @override
  void dispose() {
    _mal.dispose();
    super.dispose();
  }

  Future<void> _weiter() async {
    if (_mal.leer) {
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(tr('erst_markieren'))));
      return;
    }
    final maske = await _mal.maskePng(widget.bildBreite, widget.bildHoehe);
    if (!mounted) return;
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => WunschSeite(sitzung: Sitzung(api: widget.api, foto: widget.foto, maske: maske)),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(tr('markieren_titel'))),
      body: SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
            child: Text(tr('markieren_hinweis')),
          ),
          // Das Foto bekommt allen freien Platz; gemalt wird direkt darauf (nicht scrollbar, sonst stört das Wischen)
          Expanded(
            child: Center(
              child: Malflaeche(
                foto: widget.foto,
                bildBreite: widget.bildBreite,
                bildHoehe: widget.bildHoehe,
                steuerung: _mal,
              ),
            ),
          ),
          AnimatedBuilder(
            animation: _mal,
            builder: (context, _) => Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
              child: Row(children: [
                Text(tr('pinsel')),
                Expanded(
                  child: Slider(min: 10, max: 120, value: _mal.pinsel, onChanged: _mal.pinselSetzen),
                ),
                IconButton.outlined(
                  tooltip: tr('radierer'),
                  isSelected: _mal.radierer,
                  onPressed: _mal.radiererUmschalten,
                  icon: const Icon(Icons.auto_fix_normal),
                ),
                IconButton(
                  tooltip: tr('alles_loeschen'),
                  onPressed: _mal.allesLoeschen,
                  icon: const Icon(Icons.delete_outline),
                ),
              ]),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: FilledButton(
              onPressed: _weiter,
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
              child: Text(tr('wunsch')),
            ),
          ),
        ]),
      ),
    );
  }
}
