// 3D-Ansicht des berechneten Modells (x Breite, y Tiefe, z Höhe in mm). Ziehen dreht, Antippen wählt ein Teil,
// auseinander(f) zerlegt das Möbel (jedes Teil rückt von der Mitte weg).
import * as THREE from 'three';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const LEUCHTEN = 0x8a3410;  // gewähltes Teil

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
    this.stuecke = [];
    this.r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.r.setPixelRatio(Math.min(2, window.devicePixelRatio));
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 2.4));
    const dl = new THREE.DirectionalLight(0xffffff, 1.4); dl.position.set(1, 2, 3); this.scene.add(dl);
    this.cam = new THREE.PerspectiveCamera(30, 1.5, 10, 30000);
    this.grp = null;
    let drag = null, start = null;
    canvas.addEventListener('pointerdown', e => { drag = start = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', e => {
      if (!drag) return;
      this.rot.ry += (e.clientX - drag[0]) * 0.008;
      this.rot.rx = Math.max(-0.2, Math.min(1.3, this.rot.rx + (e.clientY - drag[1]) * 0.006));
      drag = [e.clientX, e.clientY]; this.zeichnen();
    });
    canvas.addEventListener('pointerup', e => {
      drag = null;
      // kaum bewegt: das war ein Antippen, kein Drehen
      if (start && Math.hypot(e.clientX - start[0], e.clientY - start[1]) < 6) this.antippen(e);
      start = null;
    });
    window.addEventListener('resize', () => this.zeichnen());
  }

  zeigen(modell, { kameraHalten = false } = {}) {
    this.halten = kameraHalten;
    if (this.grp) { this.scene.remove(this.grp); this.grp.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); }
    this.grp = new THREE.Group(); this.scene.add(this.grp);
    this.stuecke = [];
    this.dims = modell.dims;
    const [W, D, H] = modell.dims;
    const add = (b, color, weich) => {
      const sx = b.max[0] - b.min[0], sy = b.max[2] - b.min[2], sz = b.max[1] - b.min[1];
      const g = new THREE.BoxGeometry(sx, sy, sz);
      const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: new THREE.Color(color), transparent: !!weich, opacity: weich ? 0.5 : 1 }));
      mesh.position.set(b.min[0] + sx / 2 - W / 2, b.min[2] + sy / 2 - H / 2, D - b.max[1] + sz / 2 - D / 2);
      this.grp.add(mesh);
      const s = { teil: b, mesh, basis: mesh.position.clone(), weich: !!weich };
      if (!weich) {
        s.kante = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({ color: 0x3a3022, transparent: true, opacity: 0.4 }));
        s.kante.position.copy(mesh.position); this.grp.add(s.kante);
      }
      mesh.userData.stueck = s;
      this.stuecke.push(s);
    };
    for (const t of modell.teile) add(t, t.gurt ? (css('--gurt') || '#3b3f46') : t.ergaenzt ? css('--mark') : css('--board'));
    for (const p of modell.polster || []) add(p, css('--soft'), true);
    // Nach dem Strecken: Zerlegen und Auswahl bleiben, solange es das Teil noch gibt
    const noch = this.stuecke.find(s => !s.weich && s.teil.id === this.gewaehlt);
    this.gewaehlt = noch ? noch.teil.id : null;
    this.auseinander(this.f, false);
    this.leuchten();
    this.beiWahl?.(noch ? noch.teil : null);
    this.zeichnen();
  }

  /** Zerlegen: f von 0 (zusammen) bis 1 (weit auseinander). */
  auseinander(f, neu = true) {
    this.f = Math.max(0, Math.min(1, f));
    for (const s of this.stuecke) {
      s.mesh.position.copy(s.basis).multiplyScalar(1 + this.f * 0.9);
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
    const r = this.el.getBoundingClientRect();
    const maus = new THREE.Vector2((e.clientX - r.left) / r.width * 2 - 1, -(e.clientY - r.top) / r.height * 2 + 1);
    const strahl = new THREE.Raycaster(); strahl.setFromCamera(maus, this.cam);
    const treffer = strahl.intersectObjects(this.stuecke.filter(s => !s.weich).map(s => s.mesh))[0];
    const id = treffer ? treffer.object.userData.stueck.teil.id : null;
    this.waehlen(id === this.gewaehlt ? null : id);
  }

  zeichnen() {
    if (!this.grp || !this.el.isConnected) return;
    const w = this.el.clientWidth || 600, h = this.fuellen ? (this.el.clientHeight || Math.round(w / 1.5)) : Math.round(w / 1.5);
    this.r.setSize(w, h, false); this.cam.aspect = w / h; this.cam.updateProjectionMatrix();
    this.grp.rotation.set(this.rot.rx, this.rot.ry, 0);
    // Beim Strecken die Kamera nicht mitzoomen, sonst sieht man das Möbel nicht wachsen; beim Zerlegen weiter weg
    const weite = Math.max(...this.dims) * 2.4 * (1 + this.f * 0.8);
    this.weite = this.halten && this.weite ? Math.max(this.weite, weite) : weite;
    this.cam.position.set(0, 0, this.weite); this.cam.lookAt(0, 0, 0);
    this.grp.updateMatrixWorld();
    this.r.render(this.scene, this.cam);
  }
}

/** Bedienung über dem Viewer: Zerlegen-Regler und Anzeige des angetippten Teils. */
export function bedienung(viewer, wurzel, texte) {
  const leiste = document.createElement('div');
  leiste.className = 'bedienung';
  leiste.innerHTML = `<div class="teilinfo" aria-live="polite"></div>
    <label class="zerlegen"><span></span><input type="range" min="0" max="100" value="0"></label>`;
  leiste.querySelector('.zerlegen span').textContent = texte.zerlegen;
  const info = leiste.querySelector('.teilinfo'), regler = leiste.querySelector('input');
  regler.setAttribute('aria-label', texte.zerlegen);
  regler.addEventListener('input', () => viewer.auseinander(regler.value / 100));
  viewer.beiWahl = t => {
    info.replaceChildren();
    if (!t) { info.textContent = texte.antippen; info.classList.remove('an'); return; }
    info.classList.add('an');
    const kopf = document.createElement('b');
    kopf.textContent = (t.b ? t.b + ' · ' : '') + (t.name || '');
    const m = document.createElement('span');
    m.textContent = masse(t).join(' × ') + ' mm';
    info.append(kopf, m);
  };
  viewer.beiWahl(null);
  wurzel.appendChild(leiste);
}

export const BEDIENUNG_CSS = `
.bedienung{position:fixed;left:10px;right:10px;bottom:10px;display:flex;flex-direction:column;gap:6px;pointer-events:none;font:13px/1.3 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1c2530}
.bedienung>*{pointer-events:auto}
.teilinfo{align-self:flex-start;max-width:100%;padding:5px 10px;border-radius:8px;background:#ffffffd9;color:#5b6573}
.teilinfo.an{color:#1c2530}
.teilinfo b{display:block;font-weight:600}
.teilinfo span{font-variant-numeric:tabular-nums}
.zerlegen{display:flex;align-items:center;gap:10px;padding:4px 10px;border-radius:999px;background:#ffffffd9}
.zerlegen input{flex:1;accent-color:#c2410c;min-width:0}`;
