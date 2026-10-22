// 3D-Ansicht des berechneten Modells (x Breite, y Tiefe, z Höhe in mm). Ziehen dreht.
import * as THREE from 'three';

const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

export class Viewer3D {
  constructor(canvas) {
    this.el = canvas;
    this.rot = { rx: 0.32, ry: -0.65 };
    this.r = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
    this.r.setPixelRatio(Math.min(2, window.devicePixelRatio));
    this.scene = new THREE.Scene();
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0x667788, 2.4));
    const dl = new THREE.DirectionalLight(0xffffff, 1.4); dl.position.set(1, 2, 3); this.scene.add(dl);
    this.cam = new THREE.PerspectiveCamera(30, 1.5, 10, 30000);
    this.grp = null;
    let drag = null;
    canvas.addEventListener('pointerdown', e => { drag = [e.clientX, e.clientY]; canvas.setPointerCapture(e.pointerId); });
    canvas.addEventListener('pointermove', e => {
      if (!drag) return;
      this.rot.ry += (e.clientX - drag[0]) * 0.008;
      this.rot.rx = Math.max(-0.2, Math.min(1.3, this.rot.rx + (e.clientY - drag[1]) * 0.006));
      drag = [e.clientX, e.clientY]; this.zeichnen();
    });
    canvas.addEventListener('pointerup', () => { drag = null; });
    window.addEventListener('resize', () => this.zeichnen());
  }

  zeigen(modell) {
    if (this.grp) { this.scene.remove(this.grp); this.grp.traverse(o => { o.geometry?.dispose(); o.material?.dispose(); }); }
    this.grp = new THREE.Group(); this.scene.add(this.grp);
    this.dims = modell.dims;
    const [W, D, H] = modell.dims;
    const add = (b, color, weich) => {
      const sx = b.max[0] - b.min[0], sy = b.max[2] - b.min[2], sz = b.max[1] - b.min[1];
      const g = new THREE.BoxGeometry(sx, sy, sz);
      const mesh = new THREE.Mesh(g, new THREE.MeshLambertMaterial({ color: new THREE.Color(color), transparent: !!weich, opacity: weich ? 0.5 : 1 }));
      mesh.position.set(b.min[0] + sx / 2 - W / 2, b.min[2] + sy / 2 - H / 2, D - b.max[1] + sz / 2 - D / 2);
      this.grp.add(mesh);
      if (!weich) {
        const kante = new THREE.LineSegments(new THREE.EdgesGeometry(g), new THREE.LineBasicMaterial({ color: 0x3a3022, transparent: true, opacity: 0.4 }));
        kante.position.copy(mesh.position); this.grp.add(kante);
      }
    };
    for (const t of modell.teile) add(t, t.ergaenzt ? css('--mark') : css('--board'));
    for (const p of modell.polster || []) add(p, css('--soft'), true);
    this.zeichnen();
  }

  zeichnen() {
    if (!this.grp || !this.el.isConnected) return;
    const w = this.el.clientWidth || 600, h = Math.round(w / 1.5);
    this.r.setSize(w, h, false); this.cam.aspect = w / h; this.cam.updateProjectionMatrix();
    this.grp.rotation.set(this.rot.rx, this.rot.ry, 0);
    this.cam.position.set(0, 0, Math.max(...this.dims) * 2.4); this.cam.lookAt(0, 0, 0);
    this.r.render(this.scene, this.cam);
  }
}
