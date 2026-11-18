// Bereich markieren: mit dem Finger über die Stelle malen, an der das Möbel stehen soll.
// Steht oben auf der Entwürfe-Seite (fest, nicht scrollbar, sonst stört das Wischen beim Malen).
import 'package:flutter/material.dart';

import '../malflaeche.dart';
import '../sitzung.dart';
import '../texte.dart';

class MarkierBereich extends StatelessWidget {
  const MarkierBereich({super.key, required this.sitzung, required this.steuerung, required this.hoehe});
  final Sitzung sitzung;
  final MalSteuerung steuerung;
  final double hoehe;

  @override
  Widget build(BuildContext context) {
    return Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 6),
        child: Text(tr('markieren_hinweis'), style: Theme.of(context).textTheme.bodySmall),
      ),
      SizedBox(
        height: hoehe,
        child: Center(
          child: Malflaeche(
            foto: sitzung.foto,
            bildBreite: sitzung.bildBreite,
            bildHoehe: sitzung.bildHoehe,
            steuerung: steuerung,
          ),
        ),
      ),
      AnimatedBuilder(
        animation: steuerung,
        builder: (context, _) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
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
