// Oberfläche: Foto, Maske malen, Entwürfe und Bauplan anzeigen.
// Alles Rechnen und die Bildarbeit macht der Server (/api/v1, dieselbe API wie die App); hier nur Foto, Maske, Anzeige.
const MAXPX = 1024;
const $ = id => document.getElementById(id);
// Texte in der Sprache der Seite (vom Server eingebettet); {name} wird ersetzt
const TEXTE = JSON.parse(document.getElementById('texte')?.textContent || '{}');
const tx = (k, w = {}) => (TEXTE[`ui.${k}`] ?? k).replace(/\{(\w+)\}/g, (_, n) => w[n] ?? '');

const z = {
  schritt: 0, foto: null, messungen: [], messPunkte: [], messModus: false, tiefe: null, radierer: false, cursor: null, bereich: [1800, 900, 900],
  entwuerfe: [], njVerlauf: [], demo: false, fotoId: null, maskeId: null, gewaehlt: -1, graph: null, verlauf: [], beschaeftigt: false, ergebnis: null,
};
const maske = document.createElement('canvas');
let bild = null, viewer = null, malt = false, fotoNr = 0;

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

const API = '/api/v1';
async function api(pfad, daten, { roh = false, methode = 'POST' } = {}) {
  const res = await fetch(API + pfad, methode === 'GET' ? {} :
    { method: methode, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(daten) });
  if (roh && res.ok) return res;
  const j = await res.json().catch(() => ({ fehler: tx('serverfehler', { n: res.status }) }));
  if (!res.ok) throw new Error(j.fehler || tx('serverfehler', { n: res.status }));
  return j;
}
// Lange KI-Aufrufe sind Aufträge: starten, dann nachfragen, bis sie fertig sind
const warte = ms => new Promise(ok => setTimeout(ok, ms));
async function auftrag(pfad, daten) {
  const start = await api(pfad, daten);
  for (let i = 0; ; i++) {
    await warte(i === 0 ? 300 : 1000);
    const s = await api(`/auftraege/${start.auftrag}`, null, { methode: 'GET' });
    if (s.status === 'fertig') return { ...start, ...s.ergebnis };
    if (s.status === 'fehler') throw new Error(s.fehler);
  }
}

// ---------- Gratis-Kontingent ----------
async function kontingentLaden() {
  try {
    const k = await api('/kontingent', null, { methode: 'GET' });
    const zeige = (id, n, art) => {
      $(id).hidden = n == null;
      if (n != null) $(id).textContent = tx(n === 0 ? `${art}_0` : n === 1 ? `${art}_1` : art, { n });
    };
    zeige('frei-runden', k.runden, 'frei_runden'); zeige('frei-nj', k.nachjustieren, 'frei_nj');
  } catch { /* Anzeige ist nur ein Hinweis */ }
}

async function codeEinloesen() {
  const code = $('code-text').value.trim(); if (!code) return;
  try {
    await api('/code', { code }); $('code-text').value = ''; fehler('');
    await kontingentLaden(); $('frei-runden').textContent += ` · ${tx('code_ok')}`;
  } catch (e) { fehler(e.message); }
}
$('code-los').addEventListener('click', codeEinloesen);
$('code-text').addEventListener('keydown', e => { if (e.key === 'Enter') codeEinloesen(); });

// ---------- 1. Foto ----------
async function fotoSetzen(src, istDemo) {
  const img = await bildLaden(src);
  const s = Math.min(1, MAXPX / Math.max(img.width, img.height));
  const c = document.createElement('canvas'); c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
  c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
  const url = c.toDataURL('image/jpeg', 0.88);
  bild = await bildLaden(url);
  maske.width = c.width; maske.height = c.height; toenung = null;
  Object.assign(z, { foto: { url, w: c.width, h: c.height, demo: istDemo }, messungen: [], messPunkte: [], messModus: false,
    entwuerfe: [], graph: null, gewaehlt: -1, fotoId: null });
  // Foto gleich hochladen: Während du markierst, schätzt der Server die Tiefe fürs Messen
  const nr = ++fotoNr;
  z.tiefe = auftrag('/fotos', { foto: url })
    .then(j => { if (nr === fotoNr) z.fotoId = j.foto_id; return j; })
    .catch(() => null);  // ohne Tiefe: Maße eben von Hand
  $('arbeitsflaeche').hidden = false; $('kein-foto').hidden = true;
  fehler(''); messAnzeigen(); zeigeSchritt(1);  // direkt markieren
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

// ---------- Im Foto messen: Strecke antippen, echte Länge eingeben; der Server rechnet die Maße ----------
function messAnzeigen() {
  $('mess-start').setAttribute('aria-pressed', z.messModus);
  $('mess-start').textContent = tx(z.messungen.length ? 'mess_zweite' : 'mess_start');
  $('mess-start').hidden = z.messungen.length >= 2;
  $('mess-reset').hidden = !z.messungen.length && !z.messPunkte.length;
  $('mess-eingabe').hidden = z.messPunkte.length !== 2;
  if (z.messModus) $('mess-hinweis').textContent = tx('mess_punkt', { n: z.messPunkte.length + 1 });
  else if (!z.messungen.length) $('mess-hinweis').textContent = tx('mess_hinweis');
  zeichnen();
}
$('mess-start').addEventListener('click', () => { z.messPunkte = []; z.messModus = true; messAnzeigen(); });
$('mess-reset').addEventListener('click', () => {
  Object.assign(z, { messungen: [], messPunkte: [], messModus: false }); $('mass-hinweis').textContent = tx('mass_hinweis'); messAnzeigen();
});
function messungUebernehmen() {
  const cm = parseFloat($('mess-cm').value.replace(',', '.'));
  if (!(cm > 0) || z.messPunkte.length !== 2) return;
  z.messungen.push({ a: z.messPunkte[0], b: z.messPunkte[1], mm: cm * 10 });
  z.messPunkte = []; $('mess-cm').value = '';
  messAnzeigen(); messen();
}
$('mess-ok').addEventListener('click', messungUebernehmen);
$('mess-cm').addEventListener('keydown', e => { if (e.key === 'Enter') messungUebernehmen(); });

// ---------- 2. Bereich ----------
function zeichnen() {
  const cv = $('arbeitsflaeche'); if (!bild || cv.hidden) return;
  cv.width = bild.width; cv.height = bild.height;
  const g = cv.getContext('2d');
  g.drawImage(bild, 0, 0);
  if (!toenung || toenung.width !== cv.width) toenungNeu();
  g.drawImage(toenung, 0, 0);
  // Messstrecken wie ein Zollstock: dunkle Linie mit gelbem Kern, Länge in der Mitte
  for (const m of [...z.messungen, { a: z.messPunkte[0], b: z.messPunkte[1] }]) {
    if (!m.a) continue;
    if (m.b) {
      g.lineCap = 'round';
      g.strokeStyle = 'rgba(0,0,0,.6)'; g.lineWidth = 6; g.beginPath(); g.moveTo(...m.a); g.lineTo(...m.b); g.stroke();
      g.strokeStyle = '#e8b400'; g.lineWidth = 3; g.beginPath(); g.moveTo(...m.a); g.lineTo(...m.b); g.stroke();
    }
    for (const p of [m.a, m.b]) if (p) { g.fillStyle = '#e8b400'; g.strokeStyle = '#000'; g.lineWidth = 2; g.beginPath(); g.arc(p[0], p[1], 7, 0, 7); g.fill(); g.stroke(); }
    if (m.mm && m.b) {
      const text = `${(m.mm / 10).toLocaleString()} cm`, x = (m.a[0] + m.b[0]) / 2, y = (m.a[1] + m.b[1]) / 2;
      g.font = '600 14px monospace'; g.textAlign = 'center'; g.textBaseline = 'middle';
      const w = g.measureText(text).width + 10;
      g.fillStyle = '#1c2530'; g.fillRect(x - w / 2, y - 11, w, 22); g.fillStyle = '#fff'; g.fillText(text, x, y);
    }
  }
  if (z.cursor && z.schritt === 1 && !z.messModus) {  // Pinsel-Vorschau: Kreis in Pinselgröße, gestrichelt beim Radieren
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
  if (z.messModus) {  // Enden der Strecke setzen statt malen
    z.messPunkte.push(pos(e));
    if (z.messPunkte.length === 2) { z.messModus = false; messAnzeigen(); $('mess-cm').focus(); } else messAnzeigen();
    return;
  }
  if (z.schritt === 1) { malt = true; cv.setPointerCapture(e.pointerId); malen(e); }
});
cv.addEventListener('pointermove', e => {
  z.cursor = pos(e);
  cv.style.cursor = z.messModus ? 'crosshair' : z.schritt === 1 ? 'none' : 'default';
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
let messNr = 0;
async function messen() {
  if (!z.messungen.length || !maskenRahmen()) return;
  const nr = ++messNr;  // nur die letzte Rechnung zählt (Maske kann sich inzwischen geändert haben)
  $('mass-hinweis').textContent = tx('mess_warten');
  const tiefe = await z.tiefe;
  if (nr !== messNr) return;
  if (!tiefe) { $('mass-hinweis').textContent = tx('mass_hinweis'); return; }
  const rel = p => [p[0] / maske.width, p[1] / maske.height];
  try {
    const j = await api('/masse', {
      tiefe_id: tiefe.tiefe_id, maske: maske.toDataURL('image/png'),
      messungen: z.messungen.map(m => ({ a: rel(m.a), b: rel(m.b), mm: m.mm })) });
    if (nr !== messNr) return;
    bereichSetzen(z.bereich.map((v, i) => j.bereich[i] ?? v));
    $('mass-hinweis').textContent = [tx('gemessen'), ...j.hinweise].join(' ');
  } catch (e) { if (nr === messNr) $('mass-hinweis').textContent = e.message; }
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
    // Maske: transparent, gemalt = deckend weiß; das Foto nur beim ersten Mal hochladen
    const foto = z.fotoId ? { foto_id: z.fotoId } : { foto: z.foto.url };
    const j = await auftrag('/entwuerfe', { ...foto, maske: maske.toDataURL('image/png'), wunsch: $('wunsch').value });
    Object.assign(z, { demo: j.demo, fotoId: j.foto_id, maskeId: j.maske_id, entwuerfe: j.entwuerfe });
    $('bild-prompt').textContent = j.prompt;
    z.gewaehlt = -1; z.graph = null; z.njVerlauf = [];
    entwuerfeAnzeigen(); zeigeSchritt(3);
  } catch (e) { fehler(e.message); } finally { status(''); kontingentLaden(); }
}
function entwuerfeAnzeigen() {
  const box = $('entwuerfe'); box.replaceChildren();
  z.entwuerfe.forEach((e, i) => {
    const b = document.createElement('button');
    b.className = 'design'; b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', z.gewaehlt === i);
    const img = document.createElement('img'); img.src = e.url; img.alt = tx('entwurf', { n: i + 1 });
    const s = document.createElement('span'); s.textContent = tx('entwurf', { n: i + 1 });
    b.append(img, s);
    b.addEventListener('click', () => { z.gewaehlt = i; entwuerfeAnzeigen(); $('bauplan-erstellen').focus(); });  // Ändern ist optional
    box.append(b);
  });
  $('bauplan-erstellen').disabled = z.gewaehlt < 0;
  $('nachjustieren').hidden = z.gewaehlt < 0;
  $('nj-zurueck').disabled = !(z.njVerlauf[z.gewaehlt] || []).length;
}

// ---------- Entwurf nachjustieren (FLUX Kontext ändert das Bild, der Server setzt wieder nur den markierten Bereich ein) ----------
async function nachjustieren() {
  const i = z.gewaehlt, text = $('nj-text').value.trim();
  if (i < 0 || !text || z.beschaeftigt) return;
  status(tx('st_nachjustieren')); fehler('');
  try {
    const j = await auftrag('/entwuerfe/nachjustieren', {
      foto_id: z.fotoId, maske_id: z.maskeId, entwurf_id: z.entwuerfe[i].id, wunsch: $('wunsch').value, anpassung: text });
    (z.njVerlauf[i] ||= []).push(z.entwuerfe[i]);
    z.entwuerfe[i] = j.entwurf;
    $('bild-prompt').textContent = j.prompt; $('nj-text').value = '';
    entwuerfeAnzeigen();
  } catch (e) { fehler(e.message); } finally { status(''); kontingentLaden(); }
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
    const e = z.entwuerfe[z.gewaehlt];  // den Ausschnitt um den Bereich schneidet der Server
    const j = await auftrag('/bauplan/lesen', { entwurf_id: e.id, maske_id: z.maskeId, bereich: z.bereich, demo_index: z.demo ? z.gewaehlt : null });
    z.graph = j.graph; z.verlauf = []; $('verlauf').replaceChildren(); $('rueckgaengig').disabled = true;
    if (j.pruefung) verlauf('ai', j.pruefung.passt ? tx('geprueft_ok') : tx('geprueft', { liste: j.pruefung.maengel.join(' · ') }));
    $('gewaehlt').src = e.url;
    await berechnen();
    zeigeSchritt(4);
  } catch (e) { fehler(e.message); } finally { status(''); }
}
$('bauplan-erstellen').addEventListener('click', bauplanErstellen);

async function berechnen() {
  try {
    const j = await api('/bauplan/berechnen?mit_html=true&mit_glb=false', { graph: z.graph, bereich: z.bereich });
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
    const j = await auftrag('/bauplan/anpassen', { graph: z.graph, wunsch: text });
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
    try { herunterladen('parawerk.dxf', await (await api('/bauplan/dxf', { graph: z.graph, bereich: z.bereich }, { roh: true })).blob()); }
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
kontingentLaden();
