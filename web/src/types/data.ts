/**
 * Boru hattının ürettiği statik JSON'un şekli.
 *
 * Dosyalar `scripts/build_web_data.py` tarafından yazılır. Buradaki tipler
 * o betiğin çıktısını birebir izler; alan adı değişirse iki taraf da
 * değişmeli.
 */

/** Bir indeks grubunun PCA özeti. */
export type PcaInfo = {
  /** Gruba giren kategoriler. */
  members: string[];
  /** İlk bileşenin açıkladığı varyans yüzdesi. */
  evr: number;
  /** Bileşen yükleri — üye sırasıyla. */
  loadings: number[];
  /** Bant numarasından hücre sayısına. Boş bant burada 0 görünür. */
  bands: Record<string, number>;
  /** Model önceki veri sürümüne mi uyduruldu. */
  fittedOnPrevious: boolean;
};

export type MetroNode = {
  name: string;
  /** `kept` ya da atılma nedeni. */
  decision: string;
  /** Kararın insan tarafından okunabilir gerekçesi. */
  reason: string;
  lat: number;
  lon: number;
};

export type ValidationFinding = {
  check: string;
  severity: "info" | "warning" | "error" | string;
  message: string;
  count: number;
  /** Bulgunun düştüğü satır numaraları (uzun listeler kırpılır). */
  rows?: number[];
};

export type FileReport = {
  file: string;
  rows: number;
  columns: string[];
  /** Dosya hiç okunamadıysa nedeni; okunduysa null. */
  unreadable: string | null;
  findings: ValidationFinding[];
};

/** Bir indeksin iki sürüm arasındaki hareketi. */
export type EffectRow = {
  spearman: number;
  moved_pct: number;
  up_pct: number;
  down_pct: number;
  mean_shift: number;
  max_band_before: number;
  max_band_after: number;
};

export type Comparison = {
  cells: number;
  /** Yöntem sabit, veri yeni. */
  data_effect: Record<string, EffectRow>;
  /** Veri sabit, yöntem yeni. */
  method_effect: Record<string, EffectRow>;
};

export type CategoryCount = {
  key: string;
  new: number;
  /** Önceki sürümde karşılığı yoksa null. */
  old: number | null;
};

export type BetaRow = {
  beta: number;
  groups: string[];
  /** Çarpandan (0.5 / 2.0) oynayan hücre yüzdesine. */
  effect: Record<string, number>;
};

export type Summary = {
  meta: {
    cells: number;
    poi: number;
    categories: number;
    indices: number;
    metroKept: number;
    metroRaw: number;
    csvMb: number | null;
    resolution: number;
    mapResolutions: number[];
    bbox: number[];
  };
  groups: string[];
  pca: Record<string, PcaInfo>;
  cross: {
    /** Yedi indeks birlikte çözümlendiğinde bileşenlerin payı. */
    evr: number[];
    corr: Record<string, Record<string, number>>;
  };
  metro: { summary: Record<string, number>; nodes: MetroNode[] };
  validation: FileReport[];
  counts: CategoryCount[];
  comparison: Comparison | null;
  beta: Record<string, BetaRow> | null;
  decay: Record<string, number>;
  retired: Record<string, string>;
};

/** Bir H3 seviyesinin harita katmanı. Diziler konum konum eşleşir. */
export type CellLayer = {
  res: number;
  h3: string[];
  indices: Record<string, number[]>;
  deltas: Record<string, number[]>;
};

/** Kategori adından [enlem, boylam] listesine. */
export type PoiLayers = Record<string, [number, number][]>;
