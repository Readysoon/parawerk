// Startseite: Foto aufnehmen oder aus der Galerie wählen.
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api.dart';
import '../hilfen.dart';
import '../texte.dart';
import 'markieren.dart';

class StartSeite extends StatelessWidget {
  const StartSeite({super.key, required this.api});
  final Api api;

  Future<void> _foto(BuildContext context, ImageSource quelle) async {
    final hinweise = ScaffoldMessenger.of(context);
    final navigator = Navigator.of(context);
    try {
      // 1600 px reichen: Der Server verkleinert ohnehin auf 1024 px
      final datei = await ImagePicker().pickImage(source: quelle, maxWidth: 1600, maxHeight: 1600, imageQuality: 88);
      if (datei == null) return;
      final bytes = await datei.readAsBytes();
      final bild = (await (await ui.instantiateImageCodec(bytes)).getNextFrame()).image;
      navigator.push(MaterialPageRoute<void>(
        builder: (_) => MarkierenSeite(api: api, foto: bytes, bildBreite: bild.width, bildHoehe: bild.height),
      ));
    } catch (e) {
      hinweise.showSnackBar(SnackBar(content: Text(fehlerText(e))));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            const Spacer(),
            Text(tr('titel'), style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w700)),
            const SizedBox(height: 4),
            Container(height: 3, color: const Color(0xFFE8B400)),
            const SizedBox(height: 16),
            Text(tr('untertitel'), style: Theme.of(context).textTheme.bodyLarge),
            const Spacer(),
            FilledButton.icon(
              onPressed: () => _foto(context, ImageSource.camera),
              icon: const Icon(Icons.photo_camera),
              label: Text(tr('kamera')),
              style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            ),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () => _foto(context, ImageSource.gallery),
              icon: const Icon(Icons.photo_library),
              label: Text(tr('galerie')),
              style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(52)),
            ),
            const SizedBox(height: 24),
          ]),
        ),
      ),
    );
  }
}
