import type { CellLayer, PoiDetail, PoiInfo, PoiLayers, Summary } from "@/types/data";

/**
 * Statik veri dosyalarını okur.
 *
 * Arka uç yok: dosyalar `public/data/` altında duruyor ve boru hattı
 * tarafından üretiliyor. Bir dosya eksikse arayüz çökmemeli, o bölüm boş
 * kalmalı — bu yüzden hatalar `null` olarak dönüyor.
 */

async function loadJson<T>(name: string): Promise<T | null> {
  try {
    const response = await fetch(`/data/${name}`, { cache: "force-cache" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export function loadSummary() {
  return loadJson<Summary>("summary.json");
}

export function loadCells(resolution: number) {
  return loadJson<CellLayer>(`cells-r${resolution}.json`);
}

export function loadPoi() {
  return loadJson<PoiLayers>("poi.json");
}

let poiInfo: Promise<PoiInfo | null> | null = null;

/** Obyekt kartlarının məlumatı. İlk klikdə bir dəfə yüklənir (~1 MB). */
export function loadPoiInfo() {
  poiInfo ??= loadJson<PoiInfo>("poi-info.json");
  return poiInfo;
}

/** Yalnız http(s) keçidləri; sxemsiz ünvana https əlavə olunur. */
export function safeUrl(value: string | undefined): string | null {
  if (!value) return null;
  const url = /^[a-z][a-z0-9+.-]*:/i.test(value) ? value : `https://${value}`;
  return /^https?:\/\//i.test(url) ? url : null;
}

/** Obyektin şəkli: birbaşa keçid və ya Wikimedia Commons faylı. */
export function imageUrl(d: PoiDetail): string | null {
  if (d.image && /^https?:\/\//i.test(d.image)) return d.image;
  const file = d.commons?.startsWith("File:") ? d.commons.slice(5) : null;
  return file
    ? `https://commons.wikimedia.org/wiki/Special:FilePath/${encodeURIComponent(file)}?width=480`
    : null;
}

export function googleMapsUrl(lat: number, lon: number) {
  return `https://www.google.com/maps/search/?api=1&query=${lat.toFixed(6)},${lon.toFixed(6)}`;
}

export function osmUrl(id: string | undefined) {
  return id && /^(node|way|relation)\/\d+$/.test(id) ? `https://www.openstreetmap.org/${id}` : null;
}

/** "az:Başlıq" → Vikipediya səhifəsi. */
export function wikipediaUrl(value: string | undefined) {
  if (!value) return null;
  const [lang, ...rest] = value.split(":");
  const title = rest.join(":");
  return title && /^[a-z-]{2,12}$/.test(lang)
    ? `https://${lang}.wikipedia.org/wiki/${encodeURIComponent(title.replaceAll(" ", "_"))}`
    : null;
}

export function instagramUrl(value: string | undefined) {
  if (!value) return null;
  if (/^https?:\/\//i.test(value)) return value;
  return `https://www.instagram.com/${encodeURIComponent(value.replace(/^@/, ""))}`;
}

/** API xidmətinin ünvanı. ``NEXT_PUBLIC_API_URL`` ilə dəyişdirilə bilər. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

/** İndeks gruplarının arayüzde görünen adları. */
export const GROUP_LABELS: Record<string, string> = {
  təhsil: "Təhsil",
  nəqliyyat: "Nəqliyyat",
  turizm: "Turizm",
  yemək: "Yemək",
  istirahət: "İstirahət",
  əyləncə: "Əyləncə",
  təhlükəsizlik: "Təhlükəsizlik"
};

/** Kaynak kategorilerin arayüzde görünen adları. */
export const CATEGORY_LABELS: Record<string, string> = {
  kdgr: "Uşaq bağçası",
  schl: "Məktəb",
  univ: "Ali məktəb",
  metro: "Metro",
  bus: "Dayanacaq",
  shopping: "Ticarət mərkəzi",
  parks: "Park",
  museum: "Muzey",
  theatre: "Teatr",
  coffee: "Kafe",
  restaurant: "Restoran",
  fast_food: "Fast-food",
  bars: "Bar",
  sport: "İdman zalı",
  hotel: "Hotel",
  monuments: "Tarixi abidə",
  camera: "Təhlükəsizlik kamerası",
  fire: "Yanğından mühafizə"
};

/**
 * Hər kateqoriyanın sabit rəngi. Əvvəl rəng seçilmə sırasına görə verilirdi və
 * eyni kateqoriya hər dəfə başqa rəngdə görünürdü.
 */
export const CATEGORY_COLORS: Record<string, string> = {
  kdgr: "#e11d48",
  schl: "#db2777",
  univ: "#9333ea",
  metro: "#1d4ed8",
  bus: "#0891b2",
  shopping: "#ca8a04",
  parks: "#16a34a",
  museum: "#7c3aed",
  theatre: "#c026d3",
  coffee: "#92400e",
  restaurant: "#ea580c",
  fast_food: "#d97706",
  bars: "#be123c",
  sport: "#2563eb",
  hotel: "#0d9488",
  monuments: "#57534e",
  camera: "#475569",
  fire: "#dc2626"
};

export function categoryColor(key: string) {
  return CATEGORY_COLORS[key] ?? "#64748b";
}

export const VERSION_LABELS: Record<string, string> = {
  "2025": "2025",
  "2026": "2026",
  "2026osm": "2026 + OSM",
  walk: "2026 + OSM · piyada"
};

export function groupLabel(key: string) {
  return GROUP_LABELS[key] ?? key;
}

export function categoryLabel(key: string) {
  return CATEGORY_LABELS[key] ?? key;
}

/** 12345 → "12 345". Azərbaycan dilində üçlü ayırıcı boşluqdur. */
export function formatCount(value: number) {
  return value.toLocaleString("az-AZ");
}
