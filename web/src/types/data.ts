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
  /** Ekibin notebook'undaki tanım: ağırlık × √özdeğer (= skor–indeks korelasyonu). */
  loadings: number[];
  /** Puanlamada kullanılan ham ağırlık (birim vektör). */
  weights: number[];
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
  /** OpenStreetMap'ten eklenen. */
  osm: number;
};

export type EnrichmentRow = {
  category: string;
  local: number;
  osm: number;
  filtered: number;
  matched: number;
  added: number;
  total: number;
  growth_pct: number;
};

export type Enrichment = {
  generated: string;
  osm_elements: number;
  inside_boundary: number;
  after_dedupe: number;
  after_rules: number;
  rejected_by_reason: Record<string, number>;
  match_radius_m: Record<string, number>;
  categories: EnrichmentRow[];
  totals: { local: number; osm: number; matched: number; added: number };
};

export type H10Check = { name: string; ok: boolean; detail: string };

export type H10Verification = {
  rows: number;
  columns: number;
  groups: string[];
  checks: H10Check[];
  all_ok: boolean;
  levels: { res: number; role: string; cells: number; what: string }[];
  original_resolution: number;
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
    poiLocal: number;
    poiOsm: number;
    versions: { key: string; label: string }[];
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
  enrichment: Enrichment | null;
  h10: H10Verification | null;
  decay: Record<string, number>;
  retired: Record<string, string>;
};

/** Bir H3 seviyesinin harita katmanı. Diziler konum konum eşleşir. */
export type CellLayer = {
  res: number;
  h3: string[];
  /** Sürüm → indeks → bal dizisi. H10'da tam sayı, üst seviyelerde ortalama. */
  v: Record<string, Record<string, number[]>>;
};

export type Points = [number, number][];

/** Sürüm → kategori → [enlem, boylam]. ``osm`` yalnız eklenen nesneler. */
export type PoiLayers = {
  "2025": Record<string, Points>;
  "2026": Record<string, Points>;
  osm: Record<string, Points>;
};

/** Nesne kartı: poi.json'daki her noktanın bilgisi, aynı sırada. */
export type PoiDetail = {
  /** Standart ad. */
  n?: string;
  /** Orijinal ad (standart addan farklıysa). */
  o?: string;
  /** OSM nesnesi, "node/123". */
  id?: string;
  /** Yerel kaydın OSM karşılığı ad ilə tapıldı. */
  m?: number;
  web?: string;
  phone?: string;
  hours?: string;
  image?: string;
  commons?: string;
  wikidata?: string;
  wikipedia?: string;
  cuisine?: string;
  stars?: string;
  instagram?: string;
  addr?: string;
};

export type PoiKey = "2025" | "2026" | "osm";

export type PoiInfo = Record<PoiKey, Record<string, PoiDetail[]>>;

/** Xəritədə seçilən obyekt. */
export type PoiSelection = { key: PoiKey; category: string; index: number };
