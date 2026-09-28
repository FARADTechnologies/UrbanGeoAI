/**
 * Seçilmiş obyektlərə görə bal — brauzerdə.
 *
 * Boru xəttinin `indices.fit_group` / `fit_bands` / `apply_bands` qaydalarının
 * sətir-sətir köçürməsidir:
 *
 * 1. hər kateqoriya skoru standartlaşdırılır (orta 0, yayınma 1; sabit sütunda 1),
 * 2. birinci baş komponent (PCA) — işarə elə seçilir ki, yüklərin cəmi müsbət olsun,
 * 3. taban (ən kiçik dəyər) → 1, qalanı 9 bərabər dilimə → 2–10.
 *
 * Tək kateqoriyada 2-ci addım heç nə etmir: bal həmin kateqoriyanın öz
 * skorunun dilimidir. Seçim bir indeksin bütün üzvlərinə bərabərdirsə bu
 * fayl işlənmir — rəsmi bal birbaşa göstərilir (map-panel).
 */

const N_BANDS = 10;

/** IEEE 754 yarım dəqiqlik → number. */
function halfToFloat(h: number): number {
  const sign = h & 0x8000 ? -1 : 1;
  const exp = (h >> 10) & 0x1f;
  const frac = h & 0x3ff;
  if (exp === 0) return sign * 2 ** -14 * (frac / 1024);
  if (exp === 31) return frac ? NaN : sign * Infinity;
  return sign * 2 ** (exp - 15) * (1 + frac / 1024);
}

const scoreCache = new Map<string, Promise<Float32Array[] | null>>();

/** Bir sürümün H10 kateqoriya skorları (kateqoriya sırası ilə). */
export function loadScores(file: string, categories: number, cells: number) {
  let promise = scoreCache.get(file);
  if (!promise) {
    promise = (async () => {
      try {
        const response = await fetch(`/data/${file}`, { cache: "force-cache" });
        if (!response.ok) return null;
        const raw = new Uint16Array(await response.arrayBuffer());
        if (raw.length !== categories * cells) return null;
        const out: Float32Array[] = [];
        for (let c = 0; c < categories; c++) {
          const col = new Float32Array(cells);
          for (let i = 0; i < cells; i++) col[i] = halfToFloat(raw[c * cells + i]);
          out.push(col);
        }
        return out;
      } catch {
        return null;
      }
    })();
    scoreCache.set(file, promise);
  }
  return promise;
}

const parentCache = new Map<number, Promise<Int32Array | null>>();

/** H10 hüceyrəsinin üst səviyyədəki hüceyrəsinin sırası (cells-rN.json-da). */
export function loadParents(resolution: number) {
  let promise = parentCache.get(resolution);
  if (!promise) {
    promise = fetch(`/data/parents-r${resolution}.bin`, { cache: "force-cache" })
      .then(async (r) => (r.ok ? new Int32Array(await r.arrayBuffer()) : null))
      .catch(() => null);
    parentCache.set(resolution, promise);
  }
  return promise;
}

/** Simmetrik matrisin ən böyük məxsusi dəyərinə uyğun vektor (Jacobi). */
function topEigenvector(matrix: number[][]): number[] {
  const n = matrix.length;
  const a = matrix.map((row) => [...row]);
  const v: number[][] = Array.from({ length: n }, (_, i) =>
    Array.from({ length: n }, (_, j) => (i === j ? 1 : 0))
  );
  for (let sweep = 0; sweep < 100; sweep++) {
    let off = 0;
    for (let p = 0; p < n; p++) for (let q = p + 1; q < n; q++) off += a[p][q] ** 2;
    if (off < 1e-22) break;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        if (Math.abs(a[p][q]) < 1e-300) continue;
        const theta = (a[q][q] - a[p][p]) / (2 * a[p][q]);
        const t = Math.sign(theta || 1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1);
        const s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = a[k][p];
          const akq = a[k][q];
          a[k][p] = c * akp - s * akq;
          a[k][q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = a[p][k];
          const aqk = a[q][k];
          a[p][k] = c * apk - s * aqk;
          a[q][k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = v[k][p];
          const vkq = v[k][q];
          v[k][p] = c * vkp - s * vkq;
          v[k][q] = s * vkp + c * vkq;
        }
      }
    }
  }
  let best = 0;
  for (let i = 1; i < n; i++) if (a[i][i] > a[best][best]) best = i;
  return v.map((row) => row[best]);
}

/** numpy.quantile (xətti interpolyasiya), sıralanmış massivdə. */
function quantile(sorted: Float64Array, q: number) {
  const pos = q * (sorted.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.min(sorted.length - 1, lo + 1);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

/** numpy.rint: yarımda cütə yuvarlaqlaşdırma. */
function rint(x: number) {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

export function fitBands(index: Float64Array): { floor: number; edges: number[] } {
  let floor = Infinity;
  for (const x of index) if (x < floor) floor = x;
  const above = Float64Array.from(index.filter((x) => x > floor)).sort();
  if (above.length === 0) return { floor, edges: [] };
  const edges: number[] = [];
  for (let k = 1; k < N_BANDS - 1; k++) edges.push(quantile(above, k / (N_BANDS - 1)));
  return { floor, edges: [...new Set(edges)].sort((a, b) => a - b) };
}

export function applyBands(index: Float64Array, floor: number, edges: number[]): Uint8Array {
  const out = new Uint8Array(index.length);
  for (let i = 0; i < index.length; i++) {
    const value = index[i];
    if (value <= floor) {
      out[i] = 1;
      continue;
    }
    if (edges.length === 0) {
      out[i] = N_BANDS;
      continue;
    }
    // searchsorted(side="right"): value-dən kiçik və ya bərabər kəsim sayı.
    let lo = 0;
    let hi = edges.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (edges[mid] <= value) lo = mid + 1;
      else hi = mid;
    }
    const band =
      edges.length === N_BANDS - 2 ? lo + 2 : 2 + rint((lo / edges.length) * (N_BANDS - 2));
    out[i] = Math.min(N_BANDS, Math.max(1, band));
  }
  return out;
}

/** Seçilmiş kateqoriyaların skorlarından H10 balı. */
export function customBands(columns: Float32Array[]): Uint8Array {
  const k = columns.length;
  const n = columns[0].length;
  const z = columns.map((col) => {
    let mean = 0;
    for (const x of col) mean += x;
    mean /= n;
    let variance = 0;
    for (const x of col) variance += (x - mean) ** 2;
    const scale = Math.sqrt(variance / n) || 1;
    return Float64Array.from(col, (x) => (x - mean) / scale);
  });
  let weights = [1];
  if (k > 1) {
    const cov = Array.from({ length: k }, () => new Array<number>(k).fill(0));
    for (let a = 0; a < k; a++) {
      for (let b = a; b < k; b++) {
        let s = 0;
        const za = z[a];
        const zb = z[b];
        for (let i = 0; i < n; i++) s += za[i] * zb[i];
        cov[a][b] = cov[b][a] = s / n;
      }
    }
    weights = topEigenvector(cov);
    if (weights.reduce((s, w) => s + w, 0) < 0) weights = weights.map((w) => -w);
  }
  const index = new Float64Array(n);
  for (let a = 0; a < k; a++) {
    const w = weights[a];
    const za = z[a];
    for (let i = 0; i < n; i++) index[i] += za[i] * w;
  }
  // indices.compute_index: 10 ondalığa yuvarlama, eşit hüceyrələr eşit qalsın.
  for (let i = 0; i < n; i++) index[i] = Math.round(index[i] * 1e10) / 1e10;
  const { floor, edges } = fitBands(index);
  return applyBands(index, floor, edges);
}

/** H10 balını üst səviyyəyə ortalayır (boru xəttinin H7–H9 qaydası). */
export function aggregate(bands: Uint8Array, parents: Int32Array, size: number): number[] {
  const sum = new Float64Array(size);
  const count = new Uint32Array(size);
  for (let i = 0; i < bands.length; i++) {
    const p = parents[i];
    if (p < 0) continue;
    sum[p] += bands[i];
    count[p] += 1;
  }
  return Array.from(sum, (s, i) => (count[i] ? Math.round((s / count[i]) * 100) / 100 : 0));
}
