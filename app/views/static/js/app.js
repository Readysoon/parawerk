// Oberfläche: Foto, Maske malen, Entwürfe zusammensetzen, Bauplan anzeigen.
// Gerechnet wird auf dem Server; hier passiert nur, was ein Foto im Browser braucht.
import { a4Homography, messeMm } from './geometrie.js';

const MAXPX = 1024;
const $ = id => document.getElementById(id);
// Texte in der Sprache der Seite (vom Server eingebettet); {name} wird ersetzt
const TEXTE = JSON.parse(document.getElementById('texte')?.textContent || '{}');
const tx = (k, w = {}) => (TEXTE[`ui.${k}`] ?? k).replace(/\{(\w+)\}/g, (_, n) => w[n] ?? '');

const z = {
  schritt: 0, foto: null, a4: [], a4Modus: false, radierer: false, cursor: null, bereich: [1800, 900, 900],
  entwuerfe: [], njVerlauf: [], demo: false, gewaehlt: -1, graph: null, verlauf: [], beschaeftigt: false, ergebnis: null,
};
const maske = document.createElement('canvas');
let bild = null, viewer = null, malt = false;

const bildLaden = src => new Promise((ok, no) => { const i = new Image(); i.onload = () => ok(i); i.onerror = no; i.src = src; });

// ---------- Anzeige ----------
function zeigeSchritt(n) {
  z.schritt = n;
  document.querySelectorAll('[data-ansicht]').forEach(el => { el.hidden = !el.dataset.ansicht.split(' ').includes(String(n)); });
  const moeglich = [true, !!z.foto, !!z.foto, z.entwuerfe.length > 0, !!z.graph];
  document.querySelectorAll('nav.steps button').forEach((b, i) => {
    b.disabled = !moeglich[i];
    if (i === n) b.setAttribute('aria-current', 'step'); else b.removeAttribute('aria-current');
  });
  $('bereich-text').textContent = `${z.bereich.join(' × ')} mm`;
  zeichnen();
  if (n === 4) viewer?.zeichnen();
}
function status(text) { z.beschaeftigt = !!text; $('status').hidden = !text; $('status-text').textContent = text || ''; }
function fehler(text) { $('fehler').hidden = !text; $('fehler').textContent = text || ''; }

async function api(pfad, daten, { roh = false } = {}) {
  const res = await fetch(pfad, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(daten) });
  if (roh && res.ok) return res;
  const j = await res.json().catch(() => ({ fehler: tx('serverfehler', { n: res.status }) }));
  if (!res.ok) throw new Error(j.fehler || tx('serverfehler', { n: res.status }));
  return j;
}

// ---------- 1. Foto ----------
async function fotoSetzen(src, istDemo) {
  const img = await bildLaden(src);
  const s = Math.min(1, MAXPX / Math.max(img.width, img.height));
  const c = document.createElement('canvas'); c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  const url = c.toDataURL('image/jpeg', 0.88);
  bild = await bildLaden(url);
  maske.width = c.width; maske.height = c.height; toenung = null;
  Object.assign(z, { foto: { url, w: c.width, h: c.height, demo: istDemo }, a4: [], entwuerfe: [], graph: null, gewaehlt: -1 });
  $('arbeitsflaeche').hidden = false; $('kein-foto').hidden = true;
  fehler(''); a4Anzeigen(); zeigeSchritt(1);  // direkt markieren
}
$('foto-datei').addEventListener('change', e => {
  const f = e.target.files?.[0]; if (!f) return;
  const r = new FileReader();
  r.onload = () => fotoSetzen(r.result, false).catch(() => fehler(tx('bild_fehler')));
  r.readAsDataURL(f);
  e.target.value = '';  // dasselbe Foto noch einmal wählen können
});
$('beispielzimmer').addEventListener('click', () => fotoSetzen('/static/demo/zimmer.jpg', true));
$('anderes-foto').addEventListener('click', () => $('foto-datei').click());

function a4Anzeigen() {
  $('a4-start').setAttribute('aria-pressed', z.a4Modus);
  $('a4-reset').hidden = !z.a4.length;
  $('a4-hinweis').textContent = z.a4Modus ? tx('a4_ecke', { n: z.a4.length + 1 })
    : z.a4.length === 4 ? tx('a4_ok') : tx('a4_hinweis');
  zeichnen();
}
$('a4-start').addEventListener('click', () => { z.a4 = []; z.a4Modus = true; a4Anzeigen(); });
$('a4-reset').addEventListener('click', () => { z.a4 = []; z.a4Modus = false; a4Anzeigen(); });

// ---------- 2. Bereich ----------
function zeichnen() {
  const cv = $('arbeitsflaeche'); if (!bild || cv.hidden) return;
  cv.width = bild.width; cv.height = bild.height;
  const g = cv.getContext('2d');
  g.drawImage(bild, 0, 0);
  if (!toenung || toenung.width !== cv.width) toenungNeu();
  g.drawImage(toenung, 0, 0);
  if (z.a4.length) {
    g.strokeStyle = '#e8b400'; g.lineWidth = 3; g.beginPath();
    z.a4.forEach((p, i) => (i ? g.lineTo(...p) : g.moveTo(...p))); if (z.a4.length === 4) g.closePath(); g.stroke();
    z.a4.forEach((p, i) => {
      g.fillStyle = '#e8b400'; g.beginPath(); g.arc(p[0], p[1], 9, 0, 7); g.fill();
      g.fillStyle = '#2a2100'; g.font = '600 12px monospace'; g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillText(i + 1, p[0], p[1]);
    });
  }
  if (z.cursor && z.schritt === 1 && !z.a4Modus) {  // Pinsel-Vorschau: Kreis in Pinselgröße, gestrichelt beim Radieren
    const [x, y] = z.cursor, r = pinselRadius();
    g.setLineDash(z.radierer ? [6, 4] : []);
    g.lineWidth = 3; g.strokeStyle = 'rgba(0,0,0,.55)'; g.beginPath(); g.arc(x, y, r, 0, 7); g.stroke();
    g.lineWidth = 1.5; g.strokeStyle = '#fff'; g.beginPath(); g.arc(x, y, r, 0, 7); g.stroke();
    g.setLineDash([]);
  }
}
// gelbe Tönung der Maske nur neu rechnen, wenn sich die Maske ändert (nicht bei jeder Mausbewegung)
let toenung = null;
function toenungNeu() {
  toenung = document.createElement('canvas'); toenung.width = maske.width; toenung.height = maske.height;
  const tg = toenung.getContext('2d');
  tg.drawImage(maske, 0, 0); tg.globalCompositeOperation = 'source-in'; tg.fillStyle = 'rgba(232,180,0,.45)'; tg.fillRect(0, 0, toenung.width, toenung.height);
}
const pinselRadius = () => (+$('pinsel').value || 18) * maske.width / $('arbeitsflaeche').getBoundingClientRect().width;
let bildAngefragt = false;
const spaeterZeichnen = () => { if (!bildAngefragt) { bildAngefragt = true; requestAnimationFrame(() => { bildAngefragt = false; zeichnen(); }); } };
const pos = e => { const cv = $('arbeitsflaeche'), r = cv.getBoundingClientRect(); return [(e.clientX - r.left) * cv.width / r.width, (e.clientY - r.top) * cv.height / r.height]; };
function malen(e) {
  const [x, y] = pos(e), g = maske.getContext('2d');
  g.globalCompositeOperation = z.radierer ? 'destination-out' : 'source-over'; g.fillStyle = '#fff';
  g.beginPath(); g.arc(x, y, pinselRadius(), 0, 7); g.fill();
  toenungNeu(); spaeterZeichnen();
}
const cv = $('arbeitsflaeche');
cv.addEventListener('pointerdown', e => {
  if (!z.foto) return;
  if (z.a4Modus) {  // Ecken setzen statt malen
    if (z.a4.length < 4) z.a4.push(pos(e));
    if (z.a4.length === 4) { z.a4Modus = false; messen(); }
    a4Anzeigen(); return;
  }
  if (z.schritt === 1) { malt = true; cv.setPointerCapture(e.pointerId); malen(e); }
});
cv.addEventListener('pointermove', e => {
  z.cursor = pos(e);
  cv.style.cursor = z.schritt === 1 && !z.a4Modus ? 'none' : z.a4Modus ? 'crosshair' : 'default';
  if (malt) malen(e); else spaeterZeichnen();
});
cv.addEventListener('pointerleave', () => { z.cursor = null; spaeterZeichnen(); });
cv.addEventListener('pointerup', () => { if (malt) { malt = false; messen(); } });

function maskenRahmen() {
  if (!maske.width) return null;
  const d = maske.getContext('2d').getImageData(0, 0, maske.width, maske.height).data;
  let x0 = 1e9, y0 = 1e9, x1 = -1, y1 = -1;
  for (let y = 0; y < maske.height; y += 2) for (let x = 0; x < maske.width; x += 2) {
    if (d[(y * maske.width + x) * 4 + 3] > 10) { x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y); }
  }
  return x1 < 0 ? null : { x0, y0, x1, y1 };
}
function messen() {
  const b = maskenRahmen();
  const H = b && z.a4.length === 4 ? a4Homography(z.a4) : null;
  if (!H) { $('mass-hinweis').textContent = tx('mass_hinweis'); return; }
  const w = Math.round(messeMm(H, [b.x0, b.y1], [b.x1, b.y1]));
  const h = Math.round(messeMm(H, [(b.x0 + b.x1) / 2, b.y0], [(b.x0 + b.x1) / 2, b.y1]));
  $('mass-hinweis').textContent = tx('gemessen', { w, h });
  bereichSetzen([w, z.bereich[1], h]);
}
$('radierer').addEventListener('click', () => {
  z.radierer = !z.radierer;
  $('radierer').setAttribute('aria-pressed', z.radierer); $('radierer').textContent = tx(z.radierer ? 'radierer_an' : 'radierer');
});
$('maske-loeschen').addEventListener('click', () => { maske.getContext('2d').clearRect(0, 0, maske.width, maske.height); toenungNeu(); zeichnen(); messen(); });

function bereichSetzen(b) {
  z.bereich = b;
  document.querySelectorAll('[data-bereich]').forEach(i => { i.value = b[+i.dataset.bereich]; });
  $('bereich-text').textContent = `${b.join(' × ')} mm`;
}
let neuRechnen = null;
document.querySelectorAll('[data-bereich]').forEach(i => i.addEventListener('input', () => {
  const b = [...z.bereich]; b[+i.dataset.bereich] = +i.value || 0;
  bereichSetzen(b);
  if (z.graph && b.every(v => v > 0)) { clearTimeout(neuRechnen); neuRechnen = setTimeout(berechnen, 400); }
}));
$('zu-wunsch').addEventListener('click', () => {
  if (!maskenRahmen()) { fehler(tx('erst_markieren')); return; }
  fehler(''); zeigeSchritt(2);
});

// ---------- 3./4. Wunsch und Entwürfe ----------
document.querySelectorAll('[data-wunsch]').forEach(b => b.addEventListener('click', () => { $('wunsch').value = b.dataset.wunsch; }));

async function entwerfen() {
  const b = maskenRahmen();
  if (!b) { fehler(tx('erst_markieren')); zeigeSchritt(1); return; }
  status(tx('st_entwerfen')); fehler('');
  try {
    const mk = document.createElement('canvas'); mk.width = z.foto.w; mk.height = z.foto.h; const g = mk.getContext('2d');
    g.fillStyle = '#000'; g.fillRect(0, 0, mk.width, mk.height); g.filter = 'blur(2px)'; g.drawImage(maske, 0, 0);
    const j = await api('/api/entwuerfe', { foto: z.foto.url, maske: mk.toDataURL('image/png'), wunsch: $('wunsch').value });
    z.demo = j.demo;
    $('bild-prompt').textContent = j.prompt;
    z.entwuerfe = [];
    for (const src of j.bilder) z.entwuerfe.push(await einsetzen(src));
    z.gewaehlt = -1; z.graph = null; z.njVerlauf = [];
    entwuerfeAnzeigen(); zeigeSchritt(3);
  } catch (e) { fehler(e.message); } finally { status(''); }
}
// nur den markierten Bereich (weich ausgeblendet) aus dem Entwurf ins Originalfoto übernehmen
async function einsetzen(src) {
  const d = await bildLaden(src);
  const out = document.createElement('canvas'); out.width = bild.width; out.height = bild.height; const g = out.getContext('2d');
  g.drawImage(bild, 0, 0);
  const t = document.createElement('canvas'); t.width = bild.width; t.height = bild.height; const tg = t.getContext('2d');
  tg.drawImage(d, 0, 0, t.width, t.height);
  const m = document.createElement('canvas'); m.width = bild.width; m.height = bild.height; const mg = m.getContext('2d');
  mg.filter = 'blur(10px)'; mg.drawImage(maske, 0, 0); mg.drawImage(maske, 0, 0);
  tg.globalCompositeOperation = 'destination-in'; tg.drawImage(m, 0, 0);
  g.drawImage(t, 0, 0);
  return out.toDataURL('image/jpeg', 0.9);
}
function entwuerfeAnzeigen() {
  const box = $('entwuerfe'); box.replaceChildren();
  z.entwuerfe.forEach((src, i) => {
    const b = document.createElement('button');
    b.className = 'design'; b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', z.gewaehlt === i);
    const img = document.createElement('img'); img.src = src; img.alt = tx('entwurf', { n: i + 1 });
    const s = document.createElement('span'); s.textContent = tx('entwurf', { n: i + 1 });
    b.append(img, s);
    b.addEventListener('click', () => { z.gewaehlt = i; entwuerfeAnzeigen(); $('nj-text').focus(); });
    box.append(b);
  });
  $('bauplan-erstellen').disabled = z.gewaehlt < 0;
  $('nachjustieren').hidden = z.gewaehlt < 0;
  $('nj-zurueck').disabled = !(z.njVerlauf[z.gewaehlt] || []).length;
}

// ---------- Entwurf nachjustieren (FLUX Kontext ändert das Bild, eingesetzt wird wieder nur der markierte Bereich) ----------
async function nachjustieren() {
  const i = z.gewaehlt, text = $('nj-text').value.trim();
  if (i < 0 || !text || z.beschaeftigt) return;
  status(tx('st_nachjustieren')); fehler('');
  try {
    const j = await api('/api/entwuerfe/nachjustieren', { bild: z.entwuerfe[i], wunsch: $('wunsch').value, anpassung: text });
    (z.njVerlauf[i] ||= []).push(z.entwuerfe[i]);
    z.entwuerfe[i] = await einsetzen(j.bild);
    $('bild-prompt').textContent = j.prompt; $('nj-text').value = '';
    entwuerfeAnzeigen();
  } catch (e) { fehler(e.message); } finally { status(''); }
}
$('nj-los').addEventListener('click', nachjustieren);
$('nj-text').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); nachjustieren(); } });
$('nj-zurueck').addEventListener('click', () => {
  const v = z.njVerlauf[z.gewaehlt]; if (!v?.length) return;
  z.entwuerfe[z.gewaehlt] = v.pop(); entwuerfeAnzeigen();
});
$('entwerfen').addEventListener('click', entwerfen);
$('neu-entwerfen').addEventListener('click', entwerfen);

// ---------- 5. Bauplan ----------
async function bauplanErstellen() {
  if (z.gewaehlt < 0) return;
  status(tx('st_lesen')); fehler('');
  try {
    const b = maskenRahmen(), img = await bildLaden(z.entwuerfe[z.gewaehlt]);
    const mx = (b.x1 - b.x0) * 0.2, my = (b.y1 - b.y0) * 0.2;
    const x0 = Math.max(0, b.x0 - mx), y0 = Math.max(0, b.y0 - my), x1 = Math.min(img.width, b.x1 + mx), y1 = Math.min(img.height, b.y1 + my);
    const c = document.createElement('canvas'); c.width = x1 - x0; c.height = y1 - y0;
    c.getContext('2d').drawImage(img, x0, y0, c.width, c.height, 0, 0, c.width, c.height);
    const j = await api('/api/bauplan/lesen', { bild: c.toDataURL('image/jpeg', 0.9), bereich: z.bereich, demo_index: z.demo ? z.gewaehlt : null });
    z.graph = j.graph; z.verlauf = []; $('verlauf').replaceChildren(); $('rueckgaengig').disabled = true;
    $('gewaehlt').src = z.entwuerfe[z.gewaehlt];
    await berechnen();
    zeigeSchritt(4);
  } catch (e) { fehler(e.message); } finally { status(''); }
}
$('bauplan-erstellen').addEventListener('click', bauplanErstellen);

async function berechnen() {
  try {
    const j = await api('/api/bauplan/berechnen', { graph: z.graph, bereich: z.bereich });
    z.ergebnis = j;
    $('bauplan').innerHTML = j.html;
    const vorlage = $('bauplan').querySelector('#ergebnis-vorlage');
    $('ergebnis').replaceChildren(vorlage.content.cloneNode(true));
    viewer ||= new (await import('./viewer3d.js')).Viewer3D($('viewer'));
    viewer.zeigen(j.modell);
    fehler('');
  } catch (e) { fehler(e.message); }
}

function verlauf(cls, text) {
  const li = document.createElement('li'); li.className = cls; li.textContent = text; $('verlauf').prepend(li);
}
async function anpassen() {
  const text = $('anpassen-text').value.trim(); if (!text || !z.graph || z.beschaeftigt) return;
  verlauf('me', text); $('anpassen-text').value = ''; status(tx('st_anpassen'));
  try {
    const j = await api('/api/bauplan/anpassen', { graph: z.graph, wunsch: text });
    z.verlauf.push(z.graph); z.graph = j.graph; $('rueckgaengig').disabled = false;
    await berechnen();
    verlauf('ai', tx('geaendert'));
  } catch (e) { verlauf('err', e.message); } finally { status(''); }
}
$('anpassen').addEventListener('click', anpassen);
$('anpassen-text').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); anpassen(); } });
$('rueckgaengig').addEventListener('click', async () => {
  const g = z.verlauf.pop(); if (!g) return;
  z.graph = g; $('rueckgaengig').disabled = !z.verlauf.length;
  await berechnen(); verlauf('ai', tx('zurueckgenommen'));
});

function herunterladen(name, blob) {
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
$('ergebnis').addEventListener('click', async e => {
  const aktion = e.target.closest('[data-aktion]')?.dataset.aktion;
  if (aktion === 'drucken') window.print();
  if (aktion === 'dxf') {
    try { herunterladen('parawerk.dxf', await (await api('/api/bauplan/dxf', { graph: z.graph, bereich: z.bereich }, { roh: true })).blob()); }
    catch (err) { fehler(err.message); }
  }
  if (aktion === 'json') {
    herunterladen('parawerk.json', new Blob([JSON.stringify({ graph: z.graph, bereich: z.bereich, plan: z.ergebnis?.plan }, null, 1)], { type: 'application/json' }));
  }
});

// ---------- Navigation ----------
document.querySelectorAll('nav.steps button').forEach(b => b.addEventListener('click', () => zeigeSchritt(+b.dataset.schritt)));
document.querySelectorAll('[data-gehe]').forEach(b => b.addEventListener('click', () => zeigeSchritt(+b.dataset.gehe)));
zeigeSchritt(0);
