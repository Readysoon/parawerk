// Maße aus dem Foto: Homographie über die vier Ecken eines A4-Blatts an der Wand.

// Löst A·x = b (Gauß mit Pivotsuche)
function solveLinear(A, b) {
  const n = b.length;
  const M = A.map((row, i) => [...row, b[i]]);
  for (let c = 0; c < n; c++) {
    let p = c;
    for (let r = c + 1; r < n; r++) if (Math.abs(M[r][c]) > Math.abs(M[p][c])) p = r;
    if (Math.abs(M[p][c]) < 1e-12) return null;
    [M[c], M[p]] = [M[p], M[c]];
    for (let r = 0; r < n; r++) {
      if (r === c) continue;
      const f = M[r][c] / M[c][c];
      for (let k = c; k <= n; k++) M[r][k] -= f * M[c][k];
    }
  }
  return M.map((row, i) => row[n] / row[i]);
}

// Homographie aus 4 Punktpaaren: src → dst
function homography(src, dst) {
  const A = [], b = [];
  for (let i = 0; i < 4; i++) {
    const [x, y] = src[i], [u, v] = dst[i];
    A.push([x, y, 1, 0, 0, 0, -u * x, -u * y]); b.push(u);
    A.push([0, 0, 0, x, y, 1, -v * x, -v * y]); b.push(v);
  }
  const h = solveLinear(A, b);
  return h ? [...h, 1] : null;
}

function applyH(H, [x, y]) {
  const w = H[6] * x + H[7] * y + H[8];
  return [(H[0] * x + H[1] * y + H[2]) / w, (H[3] * x + H[4] * y + H[5]) / w];
}

// Bildpunkte der A4-Ecken (oben links, oben rechts, unten rechts, unten links) → mm in der Blattebene
export function a4Homography(ecken, quer = false) {
  const w = quer ? 297 : 210, h = quer ? 210 : 297;
  return homography(ecken, [[0, 0], [w, 0], [w, h], [0, h]]);
}

export function messeMm(H, p1, p2) {
  const a = applyH(H, p1), b = applyH(H, p2);
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}
