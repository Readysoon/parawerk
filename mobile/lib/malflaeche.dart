// Foto anzeigen und mit dem Finger den Bereich markieren.
// Striche werden in Bildpunkten des Fotos gespeichert, damit die Maske genau zum Foto passt.
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

class Strich {
  Strich(this.breite, this.radierer);
  final double breite; // in Bildpunkten des Fotos
  final bool radierer;
  final List<Offset> punkte = [];
}

class MalSteuerung extends ChangeNotifier {
  final List<Strich> striche = [];
  bool radierer = false;
  double pinsel = 40; // Durchmesser in Bildschirmpunkten

  bool get leer => !striche.any((s) => !s.radierer);

  void allesLoeschen() {
    striche.clear();
    notifyListeners();
  }

  void radiererUmschalten() {
    radierer = !radierer;
    notifyListeners();
  }

  void pinselSetzen(double wert) {
    pinsel = wert;
    notifyListeners();
  }

  void _neu(Strich s) {
    striche.add(s);
    notifyListeners();
  }

  void _weiter(Offset p) {
    striche.last.punkte.add(p);
    notifyListeners();
  }

  /// Maske als PNG in Fotogröße: transparent, markierte Fläche deckend weiß.
  Future<Uint8List> maskePng(int breite, int hoehe) async {
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    _zeichne(canvas, Offset.zero & Size(breite.toDouble(), hoehe.toDouble()), 1, const Color(0xFFFFFFFF), 1);
    final bild = await recorder.endRecording().toImage(breite, hoehe);
    final daten = await bild.toByteData(format: ui.ImageByteFormat.png);
    return daten!.buffer.asUint8List();
  }

  /// Alle Striche deckend in eine Ebene zeichnen, die Ebene dann mit [deckkraft] auflegen
  /// (so werden sich überlappende Striche nicht dunkler). [massstab] rechnet Bildpunkte in Zeichenpunkte um.
  void _zeichne(Canvas canvas, Rect flaeche, double massstab, Color farbe, double deckkraft) {
    canvas.saveLayer(flaeche, Paint()..color = Color.fromRGBO(0, 0, 0, deckkraft));
    for (final s in striche) {
      if (s.punkte.isEmpty) continue;
      final stift = Paint()
        ..color = farbe
        ..strokeWidth = s.breite * massstab
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..style = PaintingStyle.stroke
        ..blendMode = s.radierer ? BlendMode.clear : BlendMode.srcOver;
      if (s.punkte.length == 1) {
        canvas.drawCircle(s.punkte.first * massstab, s.breite * massstab / 2, stift..style = PaintingStyle.fill);
        continue;
      }
      final pfad = Path()..moveTo(s.punkte.first.dx * massstab, s.punkte.first.dy * massstab);
      for (final p in s.punkte.skip(1)) {
        pfad.lineTo(p.dx * massstab, p.dy * massstab);
      }
      canvas.drawPath(pfad, stift);
    }
    canvas.restore();
  }
}

/// Zeigt das Foto in voller Breite und darüber die markierte Fläche (gelb, halbdurchsichtig).
class Malflaeche extends StatelessWidget {
  const Malflaeche({super.key, required this.foto, required this.bildBreite, required this.bildHoehe, required this.steuerung});

  final Uint8List foto;
  final int bildBreite;
  final int bildHoehe;
  final MalSteuerung steuerung;

  @override
  Widget build(BuildContext context) {
    return AspectRatio(
      aspectRatio: bildBreite / bildHoehe,
      child: LayoutBuilder(builder: (context, groesse) {
        final massstab = groesse.maxWidth / bildBreite; // Bildpunkte → Bildschirmpunkte
        Offset imBild(Offset p) => p / massstab;
        return GestureDetector(
          onPanStart: (d) {
            steuerung._neu(Strich(steuerung.pinsel / massstab, steuerung.radierer)..punkte.add(imBild(d.localPosition)));
          },
          onPanUpdate: (d) => steuerung._weiter(imBild(d.localPosition)),
          onTapUp: (d) {
            steuerung._neu(Strich(steuerung.pinsel / massstab, steuerung.radierer)..punkte.add(imBild(d.localPosition)));
          },
          child: Stack(fit: StackFit.expand, children: [
            Image.memory(foto, fit: BoxFit.fill, gaplessPlayback: true),
            AnimatedBuilder(
              animation: steuerung,
              builder: (context, _) => CustomPaint(painter: _MaskenMaler(steuerung, massstab)),
            ),
          ]),
        );
      }),
    );
  }
}

class _MaskenMaler extends CustomPainter {
  _MaskenMaler(this.steuerung, this.massstab);
  final MalSteuerung steuerung;
  final double massstab;

  @override
  void paint(Canvas canvas, Size size) {
    steuerung._zeichne(canvas, Offset.zero & size, massstab, const Color(0xFFE8B400), 0.45);
  }

  @override
  bool shouldRepaint(covariant _MaskenMaler alt) => true;
}
