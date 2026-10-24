import 'package:flutter_test/flutter_test.dart';
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
}
