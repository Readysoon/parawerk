// Parawerk-App: Foto → Bereich markieren → Entwürfe → Bauplan. Rechnen und Bildarbeit macht der Server.
import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import 'api.dart';
import 'seiten/start.dart';
import 'texte.dart';

const zollstockGelb = Color(0xFFE8B400);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  sprache = ui.PlatformDispatcher.instance.locale.languageCode == 'de' ? 'de' : 'en';
  final api = await Api.erstellen(sprache);
  runApp(ParawerkApp(api: api));
}

class ParawerkApp extends StatelessWidget {
  const ParawerkApp({super.key, required this.api});
  final Api api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Parawerk',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: zollstockGelb, primary: const Color(0xFF1C2530)),
        scaffoldBackgroundColor: const Color(0xFFEEF0F2),
        useMaterial3: true,
      ),
      home: StartSeite(api: api),
    );
  }
}
