// Alles, was zu einem Durchgang gehört: Foto, Maske, Maße, Wunsch und die Antworten des Servers.
import 'dart:typed_data';

import 'api.dart';

class Sitzung {
  Sitzung({required this.api, required this.foto, required this.maske, required this.bildBreite,
      required this.bildHoehe, this.hochgeladen});

  final Api api;
  final Uint8List foto; // JPEG
  final Uint8List maske; // PNG in Fotogröße, deckend = markiert
  final int bildBreite;
  final int bildHoehe;

  /// Läuft schon, während markiert wird: Foto hochladen und Tiefe schätzen. null im Ergebnis = hat nicht geklappt.
  final Future<Hochgeladen?>? hochgeladen;
  List<Messung> messungen = [];
  List<int> bereich = [1800, 900, 900]; // Breite × Tiefe × Höhe in mm
  String wunsch = '';

  // vom Server
  String? fotoId;
  String? maskeId;
  List<Entwurf> entwuerfe = [];
  bool demo = false;

  /// Neue Runde Entwürfe; das Foto wird nur beim ersten Mal hochgeladen.
  Future<void> entwerfen() async {
    fotoId ??= (await hochgeladen)?.fotoId; // schon hochgeladen: nicht noch einmal schicken
    final e = await api.entwerfen(foto: fotoId == null ? foto : null, fotoId: fotoId, maske: maske, wunsch: wunsch);
    fotoId = e.fotoId;
    maskeId = e.maskeId;
    entwuerfe = e.entwuerfe;
    demo = e.demo;
  }
}
