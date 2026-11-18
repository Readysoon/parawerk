// Bereich markieren: mit dem Finger über die Stelle malen, an der das Möbel stehen soll.
// Steht oben auf der Entwürfe-Seite, Foto in voller Breite (beim Malen auf dem Foto scrollt die Seite nicht mit).
import 'package:flutter/material.dart';

import '../malflaeche.dart';
import '../sitzung.dart';
import '../texte.dart';

class MarkierBereich extends StatelessWidget {
  const MarkierBereich({super.key, required this.sitzung, required this.steuerung});
  final Sitzung sitzung;
  final MalSteuerung steuerung;

  @override
  Widget build(BuildContext context) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.only(bottom: 6),
        child: Text(tr('markieren_hinweis'), style: Theme.of(context).textTheme.bodySmall),
      ),
      ClipRRect(
        borderRadius: BorderRadius.circular(6),
        child: Malflaeche(
          foto: sitzung.foto,
          bildBreite: sitzung.bildBreite,
          bildHoehe: sitzung.bildHoehe,
          steuerung: steuerung,
        ),
      ),
      AnimatedBuilder(
        animation: steuerung,
        builder: (context, _) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Row(children: [
            Text(tr('pinsel')),
            Expanded(child: Slider(min: 10, max: 120, value: steuerung.pinsel, onChanged: steuerung.pinselSetzen)),
            IconButton.outlined(
              tooltip: tr('radierer'),
              isSelected: steuerung.radierer,
              onPressed: steuerung.radiererUmschalten,
              icon: const Icon(Icons.auto_fix_normal),
            ),
            IconButton(
              tooltip: tr('alles_loeschen'),
              onPressed: steuerung.allesLoeschen,
              icon: const Icon(Icons.delete_outline),
            ),
          ]),
        ),
      ),
    ]);
  }
}
