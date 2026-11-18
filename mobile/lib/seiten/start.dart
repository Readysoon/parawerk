// Startseite: Foto aufnehmen oder aus der Galerie wählen.
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../api.dart';
import '../hilfen.dart';
import '../konto.dart';
import '../sitzung.dart';
import '../texte.dart';
import 'entwuerfe.dart';
import 'projekte.dart';
import 'schritte.dart';

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
        settings: const RouteSettings(name: routeEntwuerfe),
        builder: (_) => EntwuerfeSeite(sitzung: Sitzung.neu(api, bytes, bild.width, bild.height)),
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
            Align(alignment: Alignment.topRight, child: KontoKnopf(api: api)),
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
            // letzte Entwürfe wieder öffnen, statt neu zu entwerfen
            ValueListenableBuilder<Sitzung?>(
              valueListenable: Sitzung.letzte,
              builder: (context, s, _) => s == null || s.entwuerfe.isEmpty
                  ? const SizedBox.shrink()
                  : Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: FilledButton.tonalIcon(
                        onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
                            settings: const RouteSettings(name: routeEntwuerfe),
                            builder: (_) => EntwuerfeSeite(sitzung: s))),
                        icon: const Icon(Icons.photo_library_outlined),
                        label: Text(tr('zurueck_entwuerfe')),
                        style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(52)),
                      ),
                    ),
            ),
            // nach der Anmeldung: gespeicherte Baupläne
            ValueListenableBuilder<bool>(
              valueListenable: api.projekteAn,
              builder: (context, an, _) => !an
                  ? const SizedBox.shrink()
                  : Padding(
                      padding: const EdgeInsets.only(top: 12),
                      child: TextButton.icon(
                        onPressed: () => Navigator.of(context)
                            .push(MaterialPageRoute<void>(builder: (_) => ProjekteSeite(api: api))),
                        icon: const Icon(Icons.folder_open),
                        label: Text(tr('meine_projekte')),
                        style: TextButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                      ),
                    ),
            ),
            const SizedBox(height: 24),
          ]),
        ),
      ),
    );
  }
}
