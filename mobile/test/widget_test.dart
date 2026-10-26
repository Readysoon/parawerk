import 'dart:ui' show Offset;

import 'package:flutter_test/flutter_test.dart';
import 'package:parawerk/api.dart';
import 'package:parawerk/texte.dart';

void main() {
  test('Texte auf Deutsch und Englisch', () {
    sprache = 'de';
    expect(tr('entwurf', {'n': 2}), 'Entwurf 2');
    expect(frei('frei_runden', 1), 'Noch 1 Gratis-Runde');
    expect(frei('frei_runden', null), isNull);
    sprache = 'en';
    expect(tr('entwurf', {'n': 2}), 'Design 2');
    expect(frei('frei_nj', 0), 'Free changes used up');
  });

  test('Messung: Punkte relativ und auf das Bild begrenzt', () {
    final m = Messung(const Offset(0.25, 0.5), const Offset(1.2, -0.1), 1850);
    expect(m.alsJson(), {
      'a': [0.25, 0.5],
      'b': [1.0, 0.0],
      'mm': 1850.0,
    });
  });
}
