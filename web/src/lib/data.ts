import type { CellLayer, PoiLayers, Summary } from "@/types/data";

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
