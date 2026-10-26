// Verbindung zum Parawerk-Server (/api/v1). Die App rechnet nichts selbst:
// Sie schickt Foto, Maske und Wunsch und bekommt fertige Bilder, Bauplan und 3D-Modell zurück.
import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';
import 'dart:ui' show Offset;

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Server-Adresse; zum Testen gegen den eigenen Rechner: flutter run --dart-define=API=http://192.168.x.x:8000
const String apiBasis = String.fromEnvironment('API', defaultValue: 'https://parawerk.fly.dev');

class ApiFehler implements Exception {
  ApiFehler(this.meldung, [this.status]);
  final String meldung;
  final int? status;

  @override
  String toString() => meldung;
}

class Entwurf {
  Entwurf(this.id, this.url);
  factory Entwurf.ausJson(Map<String, dynamic> j) => Entwurf(j['id'] as String, j['url'] as String);
  final String id;
  final String url;

  String get vollUrl => '$apiBasis$url';
}

class EntwuerfeErgebnis {
  EntwuerfeErgebnis(this.fotoId, this.maskeId, this.entwuerfe, this.demo, this.prompt);
  final String fotoId;
  final String maskeId;
  final List<Entwurf> entwuerfe;
  final bool demo;
  final String prompt;
}

class Hochgeladen {
  Hochgeladen(this.fotoId, this.tiefeId, this.flach);
  final String fotoId;
  final String tiefeId;
  final bool flach;
}

/// Eine Strecke im Foto: zwei Punkte relativ zur Bildgröße (0–1) und ihre echte Länge in mm.
class Messung {
  Messung(this.a, this.b, this.mm);
  final Offset a;
  final Offset b;
  final double mm;

  Map<String, Object> alsJson() => {
        'a': [a.dx.clamp(0.0, 1.0), a.dy.clamp(0.0, 1.0)],
        'b': [b.dx.clamp(0.0, 1.0), b.dy.clamp(0.0, 1.0)],
        'mm': mm,
      };
}

class MassErgebnis {
  MassErgebnis(this.bereich, this.nachmessen, this.hinweise);
  final List<int?> bereich; // Breite, Tiefe, Höhe in mm
  final bool nachmessen;
  final List<String> hinweise;
}

class Api {
  Api._(this.geraet, this.sprache);

  /// Geräte-ID: einmal zufällig erzeugt und gespeichert. Darauf zählt der Server die Gratis-Runden.
  final String geraet;

  /// "de" oder "en"; der Server antwortet in dieser Sprache (Bauplan, Fehlermeldungen).
  final String sprache;

  static Future<Api> erstellen(String sprache) async {
    final prefs = await SharedPreferences.getInstance();
    var id = prefs.getString('geraet');
    if (id == null) {
      final zufall = Random.secure();
      id = 'app-${List.generate(16, (_) => zufall.nextInt(256).toRadixString(16).padLeft(2, '0')).join()}';
      await prefs.setString('geraet', id);
    }
    return Api._(id, sprache);
  }

  Map<String, String> get _kopf => {'X-Geraet': geraet, 'X-Sprache': sprache, 'Content-Type': 'application/json'};

  Map<String, dynamic> _auswerten(http.Response r) {
    Map<String, dynamic> j;
    try {
      j = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    } catch (_) {
      throw ApiFehler('Server ${r.statusCode}', r.statusCode);
    }
    if (r.statusCode >= 400) throw ApiFehler((j['fehler'] ?? 'Server ${r.statusCode}').toString(), r.statusCode);
    return j;
  }

  Future<Map<String, dynamic>> _post(String pfad, Map<String, dynamic> daten) async {
    final r = await http
        .post(Uri.parse('$apiBasis$pfad'), headers: _kopf, body: jsonEncode(daten))
        .timeout(const Duration(seconds: 90));
    return _auswerten(r);
  }

  Future<Map<String, dynamic>> _get(String pfad) async {
    final r = await http.get(Uri.parse('$apiBasis$pfad'), headers: _kopf).timeout(const Duration(seconds: 30));
    return _auswerten(r);
  }

  /// Lange KI-Aufrufe sind Aufträge: starten, dann nachfragen, bis sie fertig sind.
  Future<Map<String, dynamic>> _auftrag(String pfad, Map<String, dynamic> daten) async {
    final start = await _post(pfad, daten);
    final id = start['auftrag'] as String;
    for (var i = 0; i < 300; i++) {
      await Future<void>.delayed(Duration(milliseconds: i == 0 ? 400 : 1500));
      final Map<String, dynamic> stand;
      try {
        stand = await _get('/api/v1/auftraege/$id');
      } on TimeoutException {
        continue; // kurz kein Netz: einfach weiter nachfragen
      } on http.ClientException {
        continue;
      }
      if (stand['status'] == 'fertig') return {...start, ...(stand['ergebnis'] as Map<String, dynamic>)};
      if (stand['status'] == 'fehler') throw ApiFehler((stand['fehler'] ?? '').toString());
    }
    throw ApiFehler('Timeout');
  }

  static String _dataUrl(Uint8List daten, String mime) => 'data:$mime;base64,${base64Encode(daten)}';

  /// Was dieses Gerät noch gratis hat; null = unbegrenzt (Demo-Modus).
  Future<({int? runden, int? nachjustieren})> kontingent() async {
    final j = await _get('/api/v1/kontingent');
    return (runden: j['runden'] as int?, nachjustieren: j['nachjustieren'] as int?);
  }

  /// Testcode einlösen: mehr Gratis-Runden für dieses Gerät. Antwort wie [kontingent].
  Future<({int? runden, int? nachjustieren})> codeEinloesen(String code) async {
    final j = await _post('/api/v1/code', {'code': code});
    return (runden: j['runden'] as int?, nachjustieren: j['nachjustieren'] as int?);
  }

  /// Foto hochladen. Der Server schätzt dabei die Tiefe (Entfernung jedes Bildpunkts) fürs Messen.
  /// [flach] = keine echte Tiefe (Demo, Limit oder Fehler): Messen geht dann nur wie mit einem Lineal auf dem Foto.
  Future<Hochgeladen> fotoHochladen(Uint8List foto) async {
    final j = await _auftrag('/api/v1/fotos', {'foto': _dataUrl(foto, 'image/jpeg')});
    return Hochgeladen(j['foto_id'] as String, j['tiefe_id'] as String, j['flach'] == true);
  }

  /// Breite, Tiefe, Höhe des markierten Bereichs aus 1–2 gemessenen Strecken. null = nicht messbar.
  Future<MassErgebnis> masse({
    required String tiefeId,
    required Uint8List maske,
    required List<Messung> messungen,
  }) async {
    final j = await _post('/api/v1/masse', {
      'tiefe_id': tiefeId,
      'maske': _dataUrl(maske, 'image/png'),
      'messungen': [for (final m in messungen) m.alsJson()],
    });
    return MassErgebnis(
      [for (final v in j['bereich'] as List) (v as num?)?.round()],
      j['nachmessen'] == true,
      [for (final h in (j['hinweise'] as List? ?? const [])) '$h'],
    );
  }

  /// Foto (JPEG) und Maske (PNG, deckend gemalt = hier soll das Möbel hin) → 4 fertig eingesetzte Entwürfe.
  /// Ist [fotoId] gesetzt (neue Runde mit demselben Foto), wird das Foto nicht noch einmal hochgeladen.
  Future<EntwuerfeErgebnis> entwerfen({
    Uint8List? foto,
    String? fotoId,
    required Uint8List maske,
    required String wunsch,
  }) async {
    final j = await _auftrag('/api/v1/entwuerfe', {
      if (fotoId != null) 'foto_id': fotoId else 'foto': _dataUrl(foto!, 'image/jpeg'),
      'maske': _dataUrl(maske, 'image/png'),
      'wunsch': wunsch,
    });
    return EntwuerfeErgebnis(
      j['foto_id'] as String,
      j['maske_id'] as String,
      (j['entwuerfe'] as List).map((e) => Entwurf.ausJson(e as Map<String, dynamic>)).toList(),
      j['demo'] == true,
      (j['prompt'] ?? '').toString(),
    );
  }

  Future<Entwurf> nachjustieren({
    required String fotoId,
    required String maskeId,
    required String entwurfId,
    required String wunsch,
    required String anpassung,
  }) async {
    final j = await _auftrag('/api/v1/entwuerfe/nachjustieren', {
      'foto_id': fotoId,
      'maske_id': maskeId,
      'entwurf_id': entwurfId,
      'wunsch': wunsch,
      'anpassung': anpassung,
    });
    return Entwurf.ausJson(j['entwurf'] as Map<String, dynamic>);
  }

  /// Claude liest die Konstruktion (Bauteilgraph) aus dem Entwurf und vergleicht das berechnete Modell
  /// einmal mit dem Entwurf (Selbstkontrolle). [maengel] sind die dabei korrigierten Punkte.
  Future<({Map<String, dynamic> graph, List<String> maengel})> lesen({
    required String entwurfId,
    required String maskeId,
    required List<int> bereich,
    int? demoIndex,
  }) async {
    final j = await _auftrag('/api/v1/bauplan/lesen', {
      'entwurf_id': entwurfId,
      'maske_id': maskeId,
      'bereich': bereich,
      if (demoIndex != null) 'demo_index': demoIndex,
    });
    final pruefung = j['pruefung'] as Map<String, dynamic>?;
    final maengel = ((pruefung?['maengel'] as List?) ?? const []).map((m) => '$m').toList();
    return (graph: j['graph'] as Map<String, dynamic>, maengel: maengel);
  }

  /// Bauteilgraph → Bauplan (Prüfungen, Einkauf, Zuschnitt, Montage) und 3D-Modell (glb-URL).
  /// [schnell]: Vorschau beim Ziehen eines Reglers (nur Teile, ohne 3D-Dateien, etwas weniger genau).
  Future<Map<String, dynamic>> berechnen(Map<String, dynamic> graph, List<int> bereich, {bool schnell = false}) =>
      _post(schnell ? '/api/v1/bauplan/berechnen?mit_glb=false&schnell=true' : '/api/v1/bauplan/berechnen',
          {'graph': graph, 'bereich': bereich});

  Future<Map<String, dynamic>> anpassen(Map<String, dynamic> graph, String wunsch) async {
    final j = await _auftrag('/api/v1/bauplan/anpassen', {'graph': graph, 'wunsch': wunsch});
    return j['graph'] as Map<String, dynamic>;
  }
}
