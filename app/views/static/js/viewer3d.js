// 3D-Ansicht des berechneten Modells (x Breite, y Tiefe, z Höhe in mm). Ziehen dreht, Antippen wählt ein Teil,
// auseinander(f) zerlegt das Möbel (jedes Teil rückt von der Mitte weg), verzerren(true) zeigt ein Gitter aus
// 3×3×3 Punkten: Punkt antippen wählt ihn aus, danach verschiebt jedes Ziehen (egal wo) diesen Punkt und das Möbel
// verformt sich weich mit (nur Vorschau, nicht baubar). Daneben tippen löst die Auswahl, dann dreht Ziehen wieder.
import * as THREE from 'three';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LEUCHTEN = 0x8a3410;  // gewähltes Teil
const N = 3;                // Gitterpunkte je Richtung
const idx = (i, j, k) => (i * N + j) * N + k;
const bern = t => [(1 - t) * (1 - t), 2 * t * (1 - t), t * t];  // Bernstein-Polynome 2. Grades
const spiegel = n => idx(N - 1 - Math.floor(n / (N * N)), Math.floor(n / N) % N, n % N);  // gleicher Punkt, andere Seite

/** Außenmaß eines Teils in mm, größtes zuerst (Länge × Breite × Stärke). */
export const masse = t => [0, 1, 2].map(i => Math.round(t.max[i] - t.min[i])).sort((a, b) => b - a);

export class Viewer3D {
  // fuellen: Zeichenfläche füllt den ganzen Platz (eingebettet in der App), sonst Seitenverhältnis 3:2
  constructor(canvas, { fuellen = false } = {}) {
    this.el = canvas;
    this.fuellen = fuellen;
    this.rot = { rx: 0.32, ry: -0.65 };
    this.f = 0;              // 0 = zusammengebaut, 1 = ganz zerlegt
    this.gewaehlt = null;    // id des gewählten Teils
    this.beiWahl = null;     // Rückruf (teil | null)
    this.beiVerzerren = null; // Rückruf (an: bool)
    this.stuecke = [];
    this.verzerrAn = false;
    this.aktiv = null;       // ausgewählter Gitterpunkt (Index) oder null
    this.beiPunkt = null;    // Rückruf (index | null)
    this.beiVerformt = null; // Rückruf, sobald ein Punkt wirklich verschoben wird
    // Verschiebung der Gitterpunkte als Anteil der Außenmaße: bleibt beim Strecken erhalten
    this.versatz = Array.from({ length: N ** 3 }, () => new THREE.Vector3());
    this.r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.r.setPixelRatio(Math.min(2, window.devicePixelRatio));
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 2.4));
    const dl = new THREE.DirectionalLight(0xffffff, 1.4); dl.position.set(1, 2, 3); this.scene.add(dl);
    this.cam = new THREE.PerspectiveCamera(30, 1.5, 10, 30000);
    this.grp = null;
    let drag = null, start = null;
    canvas.addEventListener('pointerdown', e => {
      canvas.setPointerCapture(e.pointerId);
      start = [e.clientX, e.clientY];
      // Punkt ausgewählt: Ziehen verschiebt ihn (statt zu drehen)
      if (this.verzerrAn && this.aktiv !== null && this.grp) { this.ziehenBeginnen(e); drag = null; return; }
      drag = start;
    });
    canvas.addEventListener('pointermove', e => {
      if (this.ziehe) { this.punktZiehen(e); return; }
      if (!drag) return;
      this.rot.ry += (e.clientX - drag[0]) * 0.008;
      this.rot.rx = Math.max(-0.2, Math.min(1.3, this.rot.rx + (e.clientY - drag[1]) * 0.006));
      drag = [e.clientX, e.clientY]; this.zeichnen();
    });
    canvas.addEventListener('pointerup', e => {
      drag = null;
      // kaum bewegt: das war ein Antippen, kein Drehen oder Ziehen
      const tipp = start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) < 6;
      start = null;
      if (this.ziehe) {
        const bewegt = this.ziehe.bewegt;
        this.ziehe = null;
        if (bewegt) { this.kantenNeu(); this.zeichnen(); }
        if (!tipp) return;
      }
      if (tipp) this.antippen(e);
    });
    window.addEventListener('resize', () => this.zeichnen());
  }

  // verzerren: true/false schaltet das Gitter; weggelassen bleibt es, wie der Nutzer es eingestellt hat
  zeigen(modell, { kameraHalten = false, verzerren } = {}) {
    this.halten = kameraHalten;
    if (this.grp) { this.scene.remove(this.grp); this.grp.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); }
    this.grp = new THREE.Group(); this.scene.add(this.grp);
    this.stuecke = [];
    this.dims = modell.dims;
    const [W, D, H] = modell.dims;
    this.gross = new THREE.Vector3(W, H, D);  // in three: x Breite, y Höhe, z Tiefe
    const add = (b, color, weich) => {
      const sx = b.max[0] - b.min[0], sy = b.max[2] - b.min[2], sz = b.max[1] - b.min[1];
      // unterteilt, damit sich lange Teile beim Verzerren biegen können
      const teile = s => Math.max(1, Math.min(40, Math.ceil(s / 60)));
      const g = new THREE.BoxGeometry(sx, sy, sz, teile(sx), teile(sy), teile(sz));
      const mitte = new THREE.Vector3(b.min[0] + sx / 2 - W / 2, b.min[2] + sy / 2 - H / 2, D - b.max[1] + sz / 2 - D / 2);
      g.translate(mitte.x, mitte.y, mitte.z);
      const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: new THREE.Color(color), transparent: !!weich, opacity: weich ? 0.5 : 1 }));
      this.grp.add(mesh);
      const s = { teil: b, mesh, mitte, weich: !!weich, orig: g.attributes.position.array.slice() };
      // Lage im Gitter (0..1) je Eckpunkt einmal vorrechnen
      const o = s.orig, uvw = new Float32Array(o.length);
      for (let q = 0; q < o.length; q += 3) {
        uvw[q] = (o[q] + W / 2) / W; uvw[q + 1] = (o[q + 1] + H / 2) / H; uvw[q + 2] = (o[q + 2] + D / 2) / D;
      }
      s.uvw = uvw;
      mesh.userData.stueck = s;
      this.stuecke.push(s);
    };
    // alle Holzteile gleich, auch die von der Engine ergänzten (Einkaufsliste und Zuschnitt markieren sie)
    for (const t of modell.teile) add(t, t.gurt ? (css('--gurt') || '#3b3f46') : css('--board'));
    for (const p of modell.polster || []) add(p, css('--soft'), true);
    // Gitterpunkte
    const kugel = new THREE.SphereGeometry(Math.max(W, D, H) * 0.022, 14, 10);
    this.punktFarben = {
      normal: new THREE.MeshBasicMaterial({ color: 0xc2410c }),
      // immer sichtbar, auch hinter Holz; „transparent“, damit er nach dem Ring (auch transparent) gezeichnet wird
      aktiv: new THREE.MeshBasicMaterial({ color: 0xffffff, depthTest: false, transparent: true }),
      partner: new THREE.MeshBasicMaterial({ color: 0xf59e6b }),
    };
    this.punkte = this.versatz.map((_, n) => {
      const p = new THREE.Mesh(kugel, this.punktFarben.normal); p.userData.n = n; this.grp.add(p); return p;
    });
    // ein weißer Ring um den ausgewählten Punkt, damit man ihn auch vor hellem Holz sieht
    this.ring = new THREE.Mesh(new THREE.SphereGeometry(Math.max(W, D, H) * 0.05, 18, 12),
      new THREE.MeshBasicMaterial({ color: 0xc2410c, transparent: true, opacity: 0.45, depthTest: false }));
    this.ring.renderOrder = 2;  // hinter dem weißen Punkt, vor dem Holz
    this.ring.visible = false; this.grp.add(this.ring);
    this.linien = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xc2410c, transparent: true, opacity: 0.45 }));
    this.grp.add(this.linien);
    this.verzerren(typeof verzerren === 'boolean' ? verzerren : this.verzerrAn, false);
    // Nach dem Strecken: Zerlegen und Auswahl bleiben, solange es das Teil noch gibt
    const noch = this.stuecke.find(s => !s.weich && s.teil.id === this.gewaehlt);
    this.gewaehlt = noch ? noch.teil.id : null;
    this.auseinander(this.f, false);
    this.leuchten();
    this.beiWahl?.(noch ? noch.teil : null);
    this.zeichnen();
  }

  /** Gitter zum Verzerren ein- oder ausblenden. Aus = Originalform. */
  verzerren(an, neu = true) {
    this.verzerrAn = !!an;
    if (!this.verzerrAn) this.versatz.forEach(v => v.set(0, 0, 0));
    for (const p of this.punkte || []) p.visible = this.verzerrAn;
    if (this.linien) this.linien.visible = this.verzerrAn;
    this.punktWaehlen(this.verzerrAn ? this.aktiv : null, false);
    if (this.grp) { this.formen(); this.kantenNeu(); }
    this.beiVerzerren?.(this.verzerrAn);
    if (neu) this.zeichnen();
  }

  /** Gitterpunkt auswählen (null = keiner). Der Spiegelpunkt auf der anderen Seite wird mit hervorgehoben. */
  punktWaehlen(n, neu = true) {
    this.aktiv = n;
    if (this.punkte) {
      const gegen = n === null ? null : spiegel(n);
      this.punkte.forEach((p, i) => {
        const art = i === n ? 'aktiv' : i === gegen ? 'partner' : 'normal';
        p.material = this.punktFarben[art];
        p.scale.setScalar(art === 'aktiv' ? 1.5 : art === 'partner' ? 1.2 : 1);
        p.renderOrder = art === 'aktiv' ? 3 : 0;
      });
      this.ring.visible = n !== null && this.verzerrAn;
      if (n !== null) this.ring.position.copy(this.punkte[n].position);
    }
    this.beiPunkt?.(n);
    if (neu) this.zeichnen();
  }

  /** Gitterpunkt am Finger: der nächste auf dem Bildschirm, höchstens 32 Pixel entfernt (kleine Punkte, Touch). */
  punktBei(e) {
    if (!this.verzerrAn || !this.punkte) return null;
    const r = this.el.getBoundingClientRect(), x = e.clientX - r.left, y = e.clientY - r.top;
    let best = null, abstand = 32;
    this.punkte.forEach((p, n) => {
      const q = p.getWorldPosition(new THREE.Vector3()).project(this.cam);
      const d = Math.hypot((q.x + 1) / 2 * r.width - x, (1 - q.y) / 2 * r.height - y);
      if (d < abstand) { abstand = d; best = n; }
    });
    return best;
  }

  /** Verzerrung zurücknehmen, Gitter bleibt sichtbar. */
  formZurueck() {
    this.versatz.forEach(v => v.set(0, 0, 0));
    this.formen(); this.kantenNeu(); this.zeichnen();
  }

  punktLage(n) {
    const i = Math.floor(n / (N * N)), j = Math.floor(n / N) % N, k = n % N, G = this.gross;
    return new THREE.Vector3(-G.x / 2 + G.x * i / (N - 1), -G.y / 2 + G.y * j / (N - 1), -G.z / 2 + G.z * k / (N - 1))
      .add(this.versatz[n].clone().multiply(G));
  }

  formen() {
    const G = this.gross, d = this.versatz.map(v => v.clone().multiply(G));
    const leer = d.every(v => v.lengthSq() < 1e-6);
    for (const s of this.stuecke) {
      const pos = s.mesh.geometry.attributes.position, a = pos.array, o = s.orig, u = s.uvw;
      if (leer) a.set(o);
      else for (let q = 0; q < a.length; q += 3) {
        const bu = bern(u[q]), bv = bern(u[q + 1]), bw = bern(u[q + 2]);
        let x = 0, y = 0, z = 0;
        for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
          const f0 = bu[i] * bv[j]; if (!f0) continue;
          for (let k = 0; k < 3; k++) { const f = f0 * bw[k], v = d[idx(i, j, k)]; x += f * v.x; y += f * v.y; z += f * v.z; }
        }
        a[q] = o[q] + x; a[q + 1] = o[q + 1] + y; a[q + 2] = o[q + 2] + z;
      }
      pos.needsUpdate = true;
      s.mesh.geometry.computeVertexNormals();
      s.mesh.geometry.computeBoundingSphere();
    }
    this.punkte?.forEach((p, n) => p.position.copy(this.punktLage(n)));
    if (this.ring && this.aktiv !== null) this.ring.position.copy(this.punkte[this.aktiv].position);
    if (this.linien) {
      const v = [], P = n => this.punktLage(n).toArray();
      for (let i = 0; i < N; i++) for (let j = 0; j < N; j++) for (let k = 0; k < N; k++) {
        if (i < N - 1) v.push(...P(idx(i, j, k)), ...P(idx(i + 1, j, k)));
        if (j < N - 1) v.push(...P(idx(i, j, k)), ...P(idx(i, j + 1, k)));
        if (k < N - 1) v.push(...P(idx(i, j, k)), ...P(idx(i, j, k + 1)));
      }
      this.linien.geometry.setAttribute('position', new THREE.Float32BufferAttribute(v, 3));
    }
  }

  /** Kanten der Bretter aus der aktuellen Form (nach dem Loslassen, beim Ziehen wäre das zu langsam). */
  kantenNeu() {
    for (const s of this.stuecke) {
      if (s.weich) continue;
      if (s.kante) { this.grp.remove(s.kante); s.kante.geometry.dispose(); s.kante.material.dispose(); }
      s.kante = new THREE.LineSegments(new THREE.EdgesGeometry(s.mesh.geometry, 20),
        new THREE.LineBasicMaterial({ color: 0x3a3022, transparent: true, opacity: 0.4 }));
      s.kante.position.copy(s.mesh.position);
      this.grp.add(s.kante);
    }
  }

  strahl(e) {
    const r = this.el.getBoundingClientRect();
    const maus = new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
    const s = new THREE.Raycaster(); s.setFromCamera(maus, this.cam);
    return s;
  }

  /** Ziehen beginnt: Ebene quer zur Blickrichtung durch den ausgewählten Punkt; der Punkt folgt dem Finger relativ. */
  ziehenBeginnen(e) {
    const welt = this.punkte[this.aktiv].getWorldPosition(new THREE.Vector3());
    const ebene = new THREE.Plane().setFromNormalAndCoplanarPoint(this.cam.getWorldDirection(new THREE.Vector3()), welt);
    const treffer = this.strahl(e).ray.intersectPlane(ebene, new THREE.Vector3());
    if (!treffer) return;
    this.ziehe = { n: this.aktiv, ebene, anfang: this.grp.worldToLocal(treffer), versatz: this.versatz[this.aktiv].clone(),
                   bewegt: false };
  }

  punktZiehen(e) {
    const p = this.strahl(e).ray.intersectPlane(this.ziehe.ebene, new THREE.Vector3());
    if (!p) return;
    if (!this.ziehe.bewegt) {
      this.ziehe.bewegt = true;
      for (const s of this.stuecke) if (s.kante) s.kante.visible = false;  // beim Ziehen zu langsam
      this.beiVerformt?.();
    }
    const n = this.ziehe.n, G = this.gross;
    const v = this.grp.worldToLocal(p).sub(this.ziehe.anfang).divide(G).add(this.ziehe.versatz);
    // links und rechts gleich: der Punkt auf der anderen Seite bewegt sich gespiegelt mit
    const gegen = spiegel(n);
    if (gegen === n) v.x = 0;
    else this.versatz[gegen].set(-v.x, v.y, v.z);
    this.versatz[n].copy(v);
    this.formen();
    this.zeichnen();
  }

  /** Zerlegen: f von 0 (zusammen) bis 1 (weit auseinander). */
  auseinander(f, neu = true) {
    this.f = Math.max(0, Math.min(1, f));
    for (const s of this.stuecke) {
      // weg von der Mitte; Teile nahe der Mitte bekommen einen Mindestweg, sonst bleiben sie liegen
      const weg = s.mitte.clone(), l = weg.length(), min = Math.max(...this.dims) * 0.12;
      if (l > 1) weg.multiplyScalar((l * 1.1 + min) / l * this.f); else weg.set(0, min * this.f, 0);
      s.mesh.position.copy(weg);
      if (s.weich) { s.mesh.material.opacity = 0.5 * (1 - this.f); s.mesh.visible = this.f < 0.95; }
      s.kante?.position.copy(s.mesh.position);
    }
    if (neu) this.zeichnen();
  }

  waehlen(id) {
    this.gewaehlt = id;
    this.leuchten();
    this.beiWahl?.(this.stuecke.find(s => !s.weich && s.teil.id === id)?.teil ?? null);
    this.zeichnen();
  }

  leuchten() {
    for (const s of this.stuecke) if (!s.weich) s.mesh.material.emissive.setHex(s.teil.id === this.gewaehlt ? LEUCHTEN : 0);
  }

  antippen(e) {
    if (!this.grp) return;
    if (this.verzerrAn) {
      const n = this.punktBei(e);
      if (n !== null) { this.punktWaehlen(n); return; }
      if (this.aktiv !== null) { this.punktWaehlen(null); return; }  // daneben getippt: Auswahl lösen
    }
    const treffer = this.strahl(e).intersectObjects(this.stuecke.filter(s => !s.weich).map(s => s.mesh))[0];
    const id = treffer ? treffer.object.userData.stueck.teil.id : null;
    this.waehlen(id === this.gewaehlt ? null : id);
  }

  zeichnen() {
    if (!this.grp || !this.el.isConnected) return;
    const w = this.el.clientWidth || 600, h = this.fuellen ? (this.el.clientHeight || Math.round(w / 1.5)) : Math.round(w / 1.5);
    this.r.setSize(w, h, false); this.cam.aspect = w / h; this.cam.updateProjectionMatrix();
    this.grp.rotation.set(this.rot.rx, this.rot.ry, 0);
    // Beim Strecken die Kamera nicht mitzoomen, sonst sieht man das Möbel nicht wachsen; beim Zerlegen nur etwas weiter weg, damit die Teile sichtbar auseinandergehen
    const weite = Math.max(...this.dims) * 2.4 * (1 + this.f * 0.3);
    this.weite = this.halten && this.weite ? Math.max(this.weite, weite) : weite;
    this.cam.position.set(0, 0, this.weite); this.cam.lookAt(0, 0, 0);
    this.grp.updateMatrixWorld();
    this.r.render(this.scene, this.cam);
  }
}

/** Bedienung über dem Viewer: angetipptes Teil, darunter eine Leiste mit Zerlegen (Regler) und Verzerren (Schalter);
 * beim Verzerren zusätzlich „Form zurücksetzen“. */
export function bedienung(viewer, wurzel, texte) {
  const leiste = document.createElement('div');
  leiste.className = 'bedienung';
  leiste.innerHTML = `<div class="zeile1"><div class="teilinfo" aria-live="polite"></div><button type="button" class="formzurueck" hidden></button></div>
    <div class="werkzeug">
      <label class="zerlegen"><span class="z"></span><input type="range" min="0" max="100" value="0"></label>
      <label class="schalter"><span class="v"></span><input type="checkbox" role="switch"><i aria-hidden="true"></i></label>
    </div>`;
  leiste.querySelector('.z').textContent = texte.zerlegen;
  leiste.querySelector('.v').textContent = texte.verzerren || 'Verzerren';
  const info = leiste.querySelector('.teilinfo'), regler = leiste.querySelector('input[type=range]');
  const schalter = leiste.querySelector('input[type=checkbox]'), zurueck = leiste.querySelector('.formzurueck');
  regler.setAttribute('aria-label', texte.zerlegen);
  regler.addEventListener('input', () => viewer.auseinander(regler.value / 100));
  schalter.addEventListener('change', () => viewer.verzerren(schalter.checked));
  zurueck.textContent = texte.form_zurueck || '↺';
  zurueck.addEventListener('click', () => viewer.formZurueck());
  // ohne gewähltes Teil: Hinweis, was man gerade tun kann
  const hinweis = () => !viewer.verzerrAn ? texte.antippen
    : viewer.aktiv === null ? (texte.punkt_waehlen || texte.ziehen) : (texte.punkt_ziehen || texte.ziehen);
  viewer.beiWahl = t => {
    info.replaceChildren();
    if (!t) { info.textContent = hinweis(); info.classList.remove('an'); return; }
    info.classList.add('an');
    const kopf = document.createElement('b');
    kopf.textContent = (t.b ? t.b + ' · ' : '') + (t.name || '');
    const m = document.createElement('span');
    m.textContent = masse(t).join(' × ') + ' mm';
    info.append(kopf, m);
  };
  viewer.beiPunkt = () => { if (viewer.gewaehlt === null) viewer.beiWahl(null); };
  // Hinweis beim ersten Verformen (einmal je Seitenaufruf): krumme Form = gefräste Teile statt Baumarkt-Bretter
  let gezeigt = false;
  viewer.beiVerformt = () => {
    if (gezeigt || !texte.cnc_titel) return;
    gezeigt = true;
    const pop = document.createElement('div');
    pop.className = 'cnc-pop';
    pop.setAttribute('role', 'dialog');
    pop.setAttribute('aria-modal', 'true');
    pop.innerHTML = `<div class="karte"><b></b><p></p><div class="knoepfe">
      <button type="button" class="zurueck"></button><button type="button" class="ok"></button></div></div>`;
    pop.querySelector('b').textContent = texte.cnc_titel;
    pop.querySelector('p').textContent = texte.cnc_text;
    const ok = pop.querySelector('.ok'), zur = pop.querySelector('.zurueck');
    ok.textContent = texte.verstanden;
    zur.textContent = texte.form_zurueck;
    ok.addEventListener('click', () => pop.remove());
    zur.addEventListener('click', () => { viewer.formZurueck(); pop.remove(); });
    wurzel.appendChild(pop);
    ok.focus();
  };
  viewer.beiVerzerren = an => {
    zurueck.hidden = !an;
    schalter.checked = an;
    if (viewer.gewaehlt === null) viewer.beiWahl(null);
  };
  viewer.beiWahl(null);
  wurzel.appendChild(leiste);
}

// Leiste im Blau des „Weiter“-Knopfs der App (#1C2530), Gitterpunkte bleiben orange
export const BEDIENUNG_CSS = `
.bedienung{position:fixed;left:10px;right:10px;bottom:10px;display:flex;flex-direction:column;gap:6px;pointer-events:none;font:13px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1c2530}
.bedienung .zeile1{display:flex;gap:6px;align-items:flex-end;justify-content:space-between}
.bedienung .zeile1>*,.bedienung .werkzeug{pointer-events:auto}
.teilinfo{max-width:100%;padding:5px 10px;border-radius:8px;background:#ffffffd9;color:#5b6573}
.teilinfo.an{color:#1c2530}
.teilinfo b{display:block;font-weight:600}
.teilinfo span{font-variant-numeric:tabular-nums}
.formzurueck{flex:none;white-space:nowrap;font:inherit;border:0;border-radius:999px;padding:6px 12px;background:#ffffffd9;color:#c2410c;font-weight:600}
.werkzeug{display:flex;align-items:center;gap:14px;padding:6px 14px;border-radius:999px;background:#1c2530;color:#fff;box-shadow:0 2px 8px #0003}
.werkzeug label{display:flex;align-items:center;gap:8px;font-weight:600;white-space:nowrap}
.zerlegen{flex:1;min-width:0}
.zerlegen input{flex:1;min-width:0;accent-color:#fff}
.schalter{flex:none;cursor:pointer;border-left:1px solid #ffffff40;padding-left:14px}
.schalter input{position:absolute;opacity:0;width:1px;height:1px}
.schalter i{position:relative;width:38px;height:22px;border-radius:999px;background:#ffffff40;transition:background .15s}
.schalter i::after{content:"";position:absolute;top:3px;left:3px;width:16px;height:16px;border-radius:50%;background:#fff;transition:transform .15s}
.schalter input:checked+i{background:#c2410c}
.schalter input:checked+i::after{transform:translateX(16px)}
.schalter input:focus-visible+i{outline:2px solid #fff;outline-offset:2px}
.cnc-pop{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;padding:16px;background:#1c253059;font:14px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;z-index:10}
.cnc-pop .karte{max-width:340px;padding:16px 18px;border-radius:14px;background:#fff;color:#1c2530;box-shadow:0 8px 30px #0004}
.cnc-pop b{display:block;font-size:16px;margin-bottom:6px}
.cnc-pop p{margin:0 0 14px;color:#3d4753}
.cnc-pop .knoepfe{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
.cnc-pop button{font:inherit;font-weight:600;border-radius:999px;padding:8px 14px;border:0;cursor:pointer}
.cnc-pop .ok{background:#1c2530;color:#fff}
.cnc-pop .zurueck{background:transparent;color:#c2410c}`;
