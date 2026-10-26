// Im Foto messen: eine Strecke antippen und ihre echte Länge eingeben. Der Server rechnet daraus
// Breite, Tiefe und Höhe des markierten Bereichs (mit der Tiefe, die er beim Hochladen geschätzt hat).
import 'package:flutter/material.dart';

import '../api.dart';
import '../hilfen.dart';
import '../sitzung.dart';
import '../texte.dart';

const _gelb = Color(0xFFE8B400);
const _lupeAbstand = 90.0; // Lupe so weit über dem Finger, damit er sie nicht verdeckt

class MessenSeite extends StatefulWidget {
  const MessenSeite({super.key, required this.sitzung});
  final Sitzung sitzung;

  @override
  State<MessenSeite> createState() => _MessenSeiteState();
}

class _MessenSeiteState extends State<MessenSeite> {
  late final List<Messung> _messungen = [...widget.sitzung.messungen];
  final List<Offset> _punkte = []; // Enden der Strecke, die gerade entsteht (relativ 0–1)
  Offset? _finger; // relativ, solange der Finger liegt (dann zeigt die Lupe die Stelle)

  Sitzung get _s => widget.sitzung;

  Future<void> _punkt(Offset rel) async {
    if (_messungen.length >= 2) return;
    setState(() {
      _punkte.add(Offset(rel.dx.clamp(0.0, 1.0), rel.dy.clamp(0.0, 1.0)));
      _finger = null;
    });
    if (_punkte.length < 2) return;
    final cm = await _laengeFragen();
    if (!mounted) return;
    setState(() {
      if (cm != null && cm > 0) _messungen.add(Messung(_punkte[0], _punkte[1], cm * 10));
      _punkte.clear();
    });
  }

  Future<double?> _laengeFragen() async {
    final eingabe = TextEditingController();
    final text = await showDialog<String>(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        title: Text(tr('mess_laenge')),
        content: TextField(
          controller: eingabe,
          autofocus: true,
          keyboardType: const TextInputType.numberWithOptions(decimal: true),
          decoration: const InputDecoration(suffixText: 'cm'),
          onSubmitted: (v) => Navigator.of(context).pop(v),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(), child: Text(tr('abbrechen'))),
          FilledButton(onPressed: () => Navigator.of(context).pop(eingabe.text), child: Text(tr('mess_ok'))),
        ],
      ),
    );
    return double.tryParse((text ?? '').replaceAll(',', '.').trim());
  }

  Future<void> _fertig() async {
    final ergebnis = await mitWarten(context, tr('st_messen'), () async {
      final h = await _s.hochgeladen;
      if (h == null) throw ApiFehler(tr('mess_kein_foto'));
      return _s.api.masse(tiefeId: h.tiefeId, maske: _s.maske, messungen: _messungen);
    });
    if (ergebnis == null || !mounted) return;
    _s.messungen = [..._messungen];
    Navigator.of(context).pop(ergebnis);
  }

  String get _hinweis {
    if (_punkte.length == 1) return tr('messen_punkt', {'n': 2});
    if (_messungen.length == 1) return tr('messen_zweite');
    return tr('messen_hinweis');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text(tr('im_foto_messen'))),
      body: SafeArea(
        child: Column(children: [
          Padding(padding: const EdgeInsets.fromLTRB(16, 4, 16, 8), child: Text(_hinweis)),
          Expanded(
            child: Center(
              child: AspectRatio(
                aspectRatio: _s.bildBreite / _s.bildHoehe,
                child: LayoutBuilder(builder: (context, groesse) {
                  final w = groesse.maxWidth, h = groesse.maxHeight;
                  Offset rel(Offset p) => Offset(p.dx / w, p.dy / h);
                  final f = _finger;
                  return GestureDetector(
                    onTapUp: (d) => _punkt(rel(d.localPosition)),
                    onPanStart: (d) => setState(() => _finger = rel(d.localPosition)),
                    onPanUpdate: (d) => setState(() => _finger = rel(d.localPosition)),
                    onPanEnd: (_) {
                      if (_finger != null) _punkt(_finger!);
                    },
                    child: Stack(clipBehavior: Clip.none, fit: StackFit.expand, children: [
                      Image.memory(_s.foto, fit: BoxFit.fill, gaplessPlayback: true),
                      Opacity(
                        opacity: 0.35,
                        child: ColorFiltered(
                          colorFilter: const ColorFilter.mode(_gelb, BlendMode.srcIn),
                          child: Image.memory(_s.maske, fit: BoxFit.fill, gaplessPlayback: true),
                        ),
                      ),
                      CustomPaint(painter: _StreckenMaler(_messungen, _punkte, f)),
                      if (f != null)
                        Positioned(
                          left: f.dx * w - 55,
                          top: f.dy * h - 55 - _lupeAbstand,
                          child: const RawMagnifier(
                            size: Size(110, 110),
                            magnificationScale: 2.5,
                            focalPointOffset: Offset(0, _lupeAbstand),
                            decoration: MagnifierDecoration(
                              shape: CircleBorder(side: BorderSide(color: _gelb, width: 3)),
                            ),
                          ),
                        ),
                    ]),
                  );
                }),
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(16),
            child: Row(children: [
              OutlinedButton(
                onPressed: _messungen.isEmpty && _punkte.isEmpty
                    ? null
                    : () => setState(() {
                          _messungen.clear();
                          _punkte.clear();
                        }),
                style: OutlinedButton.styleFrom(minimumSize: const Size(0, 52)),
                child: Text(tr('zuruecksetzen')),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: FilledButton(
                  onPressed: _messungen.isEmpty ? null : _fertig,
                  style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                  child: Text(tr('mess_fertig')),
                ),
              ),
            ]),
          ),
        ]),
      ),
    );
  }
}

/// Strecken wie ein Zollstock: dunkle Linie mit gelbem Kern, Länge in der Mitte; dazu ein Fadenkreuz unter dem Finger.
class _StreckenMaler extends CustomPainter {
  _StreckenMaler(this.messungen, this.punkte, this.finger);
  final List<Messung> messungen;
  final List<Offset> punkte;
  final Offset? finger;

  @override
  void paint(Canvas canvas, Size size) {
    Offset px(Offset rel) => Offset(rel.dx * size.width, rel.dy * size.height);
    final rand = Paint()
      ..color = Colors.black54
      ..strokeWidth = 6
      ..strokeCap = StrokeCap.round;
    final kern = Paint()
      ..color = _gelb
      ..strokeWidth = 3
      ..strokeCap = StrokeCap.round;
    final punktFarbe = Paint()..color = _gelb;
    final punktRand = Paint()
      ..color = Colors.black
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;

    void ende(Offset p) {
      canvas.drawCircle(px(p), 7, punktFarbe);
      canvas.drawCircle(px(p), 7, punktRand);
    }

    for (final m in messungen) {
      canvas.drawLine(px(m.a), px(m.b), rand);
      canvas.drawLine(px(m.a), px(m.b), kern);
      ende(m.a);
      ende(m.b);
      final cm = m.mm / 10;
      final text = TextPainter(
        text: TextSpan(
          text: ' ${cm == cm.roundToDouble() ? cm.round() : cm} cm ',
          style: const TextStyle(color: Colors.white, backgroundColor: Color(0xFF1C2530), fontSize: 13, fontWeight: FontWeight.w600),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      final mitte = (px(m.a) + px(m.b)) / 2;
      text.paint(canvas, mitte - Offset(text.width / 2, text.height / 2));
    }
    for (final p in punkte) {
      ende(p);
    }
    final f = finger;
    if (f != null) {
      final kreuz = Paint()
        ..color = Colors.red
        ..strokeWidth = 1;
      final c = px(f);
      canvas.drawLine(c - const Offset(12, 0), c + const Offset(12, 0), kreuz);
      canvas.drawLine(c - const Offset(0, 12), c + const Offset(0, 12), kreuz);
      if (punkte.length == 1) canvas.drawLine(px(punkte.first), c, kern);
    }
  }

  @override
  bool shouldRepaint(covariant _StreckenMaler alt) => true;
}
