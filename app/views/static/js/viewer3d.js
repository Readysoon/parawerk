// 3D-Ansicht des berechneten Modells (x Breite, y Tiefe, z Höhe in mm). Ziehen dreht, Antippen wählt ein Teil,
// auseinander(f) zerlegt das Möbel (jedes Teil rückt von der Mitte weg), verzerren(true) zeigt ein Gitter aus
// 3×3×3 Punkten: Zieht man einen Punkt, verformt sich das ganze Möbel weich mit (nur Vorschau, nicht baubar).
import * as THREE from 'three';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LEUCHTEN = 0x8a3410;  // gewähltes Teil
const N = 3;                // Gitterpunkte je Richtung
const idx = (i, j, k) => (i * N + j) * N + k;
const bern = t => [(1 - t) * (1 - t), 2 * t * (1 - t), t * t];  // Bernstein-Polynome 2. Grades

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
      if (this.punktGreifen(e)) { drag = null; return; }
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
      if (this.ziehe) { this.ziehe = null; this.kantenNeu(); this.zeichnen(); start = null; return; }
      // kaum bewegt: das war ein Antippen, kein Drehen
      if (start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) < 6) this.antippen(e);
      start = null;
    });
    window.addEventListener('resize', () => this.zeichnen());
  }

  zeigen(modell, { kameraHalten = false, verzerren = false } = {}) {
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
    for (const t of modell.teile) add(t, t.gurt ? (css('--gurt') || '#3b3f46') : t.ergaenzt ? css('--mark') : css('--board'));
    for (const p of modell.polster || []) add(p, css('--soft'), true);
    // Gitterpunkte
    const kugel = new THREE.SphereGeometry(Math.max(W, D, H) * 0.022, 14, 10);
    const farbe = new THREE.MeshBasicMaterial({ color: 0xc2410c });
    this.punkte = this.versatz.map((_, n) => { const p = new THREE.Mesh(kugel, farbe); p.userData.n = n; this.grp.add(p); return p; });
    this.linien = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0xc2410c, transparent: true, opacity: 0.45 }));
    this.grp.add(this.linien);
    this.verzerren(verzerren, false);
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
    if (this.grp) { this.formen(); this.kantenNeu(); }
    this.beiVerzerren?.(this.verzerrAn);
    if (neu) this.zeichnen();
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

  punktGreifen(e) {
    if (!this.verzerrAn || !this.grp) return false;
    const t = this.strahl(e).intersectObjects(this.punkte)[0];
    if (!t) return false;
    const welt = t.object.getWorldPosition(new THREE.Vector3());
    const ebene = new THREE.Plane().setFromNormalAndCoplanarPoint(this.cam.getWorldDirection(new THREE.Vector3()), welt);
    this.ziehe = { n: t.object.userData.n, ebene };
    for (const s of this.stuecke) if (s.kante) s.kante.visible = false;
    return true;
  }

  punktZiehen(e) {
    const p = this.strahl(e).ray.intersectPlane(this.ziehe.ebene, new THREE.Vector3());
    if (!p) return;
    const n = this.ziehe.n, G = this.gross;
    this.versatz[n].set(0, 0, 0);
    const v = this.grp.worldToLocal(p).sub(this.punktLage(n)).divide(G);
    // links und rechts gleich: der Punkt auf der anderen Seite bewegt sich gespiegelt mit
    const i = Math.floor(n / (N * N)), j = Math.floor(n / N) % N, k = n % N, gegen = idx(N - 1 - i, j, k);
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

/** Bedienung über dem Viewer: Zerlegen-Regler, angetipptes Teil, beim Verzerren „Form zurücksetzen“. */
export function bedienung(viewer, wurzel, texte) {
  const leiste = document.createElement('div');
  leiste.className = 'bedienung';
  leiste.innerHTML = `<div class="zeile1"><div class="teilinfo" aria-live="polite"></div><button type="button" class="formzurueck" hidden></button></div>
    <label class="zerlegen"><span></span><input type="range" min="0" max="100" value="0"></label>`;
  leiste.querySelector('.zerlegen span').textContent = texte.zerlegen;
  const info = leiste.querySelector('.teilinfo'), regler = leiste.querySelector('input'), zurueck = leiste.querySelector('.formzurueck');
  regler.setAttribute('aria-label', texte.zerlegen);
  regler.addEventListener('input', () => viewer.auseinander(regler.value / 100));
  zurueck.textContent = texte.form_zurueck || '↺';
  zurueck.addEventListener('click', () => viewer.formZurueck());
  viewer.beiVerzerren = an => { zurueck.hidden = !an; };
  viewer.beiWahl = t => {
    info.replaceChildren();
    if (!t) { info.textContent = viewer.verzerrAn && texte.ziehen ? texte.ziehen : texte.antippen; info.classList.remove('an'); return; }
    info.classList.add('an');
    const kopf = document.createElement('b');
    kopf.textContent = (t.b ? t.b + ' · ' : '') + (t.name || '');
    const m = document.createElement('span');
    m.textContent = masse(t).join(' × ') + ' mm';
    info.append(kopf, m);
  };
  const wahl = viewer.beiWahl, verz = viewer.beiVerzerren;
  viewer.beiVerzerren = an => { verz(an); if (viewer.gewaehlt === null) wahl(null); };
  viewer.beiWahl(null);
  wurzel.appendChild(leiste);
}

export const BEDIENUNG_CSS = `
.bedienung{position:fixed;left:10px;right:10px;bottom:10px;display:flex;flex-direction:column;gap:6px;pointer-events:none;font:13px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1c2530}
.bedienung .zeile1{display:flex;gap:6px;align-items:flex-end;justify-content:space-between}
.bedienung .zeile1>*,.bedienung>label{pointer-events:auto}
.teilinfo{max-width:100%;padding:5px 10px;border-radius:8px;background:#ffffffd9;color:#5b6573}
.teilinfo.an{color:#1c2530}
.teilinfo b{display:block;font-weight:600}
.teilinfo span{font-variant-numeric:tabular-nums}
.formzurueck{flex:none;white-space:nowrap;font:inherit;border:0;border-radius:999px;padding:6px 12px;background:#ffffffd9;color:#c2410c;font-weight:600}
.zerlegen{display:flex;align-items:center;gap:10px;padding:4px 10px;border-radius:999px;background:#ffffffd9}
.zerlegen input{flex:1;accent-color:#c2410c;min-width:0}`;
