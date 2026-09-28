"use client";

import type { Layer, PickingInfo } from "@deck.gl/core";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import { useCallback, useMemo, useRef, useState } from "react";
import Map from "react-map-gl/maplibre";

import { useTheme } from "@/components/theme-provider";
import { categoryColor, categoryLabel, groupLabel, VERSION_LABELS } from "@/lib/data";
import type { CellLayer, PoiKey, PoiSelection, Points } from "@/types/data";

import { type CardTarget, PoiCard } from "./poi-card";

import "maplibre-gl/dist/maplibre-gl.css";

const INITIAL_VIEW_STATE = {
  longitude: 49.8671,
  latitude: 40.4093,
  zoom: 10.2,
  pitch: 0,
  bearing: 0
};

// Alt harita arayüzün temasını izler.
const MAP_STYLE_DARK = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const MAP_STYLE_LIGHT = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

type RGB = [number, number, number];

/** Bal rampası — platformun turuncu ölçeğinin aynısı. */
const BAND_RAMP: RGB[] = [
  [254, 243, 199],
  [253, 211, 77],
  [245, 158, 11],
  [234, 88, 12],
  [214, 95, 20],
  [130, 43, 17]
];

/** Fark rampası: aşağı düşen kırmızı, yükselen yeşil. */
const DOWN: RGB = [214, 57, 57];
const FLAT: RGB = [148, 163, 184];
const UP: RGB = [47, 179, 68];

function mix(a: RGB, b: RGB, t: number): RGB {
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t)
  ];
}

/** Rampadan sürekli renk. `ratio` 0–1 aralığına kırpılır. */
function sample(ramp: RGB[], ratio: number): RGB {
  const t = Math.max(0, Math.min(1, ratio)) * (ramp.length - 1);
  const i = Math.min(ramp.length - 2, Math.floor(t));
  return mix(ramp[i], ramp[i + 1], t - i);
}

function hexToRgb(hex: string): RGB {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export type MapMode = "band" | "delta";

export type PoiLayer = {
  category: string;
  points: Points;
  /** Yerel nokta dolu daire, OSM eklemesi halka olarak çizilir. */
  kind: "local" | "osm";
  /** Kart məlumatının açarı (poi-info.json). */
  key: PoiKey;
};

type Props = {
  layer: CellLayer;
  group: string;
  mode: MapMode;
  /** Bal modunda gösterilen sürüm. */
  version: string;
  /** Dəyişim modunda [önceki, sonraki] sürüm. */
  compare: [string, string];
  pois: PoiLayer[];
  groups: string[];
  /** Kartdakı «Cədvəldə göstər». */
  onShowInTable?: (selection: PoiSelection) => void;
  /** Seçilmiş obyektlərə görə bal: verilərsə indeksin balı yerinə göstərilir. */
  override?: { values: number[]; label: string } | null;
};

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function fmt(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

/** H10 hüceyrə sərhədləri bu yaxınlaşmadan sonra çəkilir; uzaqdan baxanda xətt
 *  sıxlığı xəritəni boğur, yaxından baxanda isə sərhədsiz eyni rəngli hüceyrələr
 *  tək bir ləkəyə çevrilir. */
const EDGE_ZOOM = 12.5;

export function IndexMap({
  layer,
  group,
  mode,
  version,
  compare,
  pois,
  groups,
  onShowInTable,
  override
}: Props) {
  const { theme } = useTheme();
  const isBase = layer.res >= 10;
  const tipRef = useRef<HTMLDivElement>(null);
  const [zoomedIn, setZoomedIn] = useState(false);
  const [card, setCard] = useState<CardTarget | null>(null);
  const closeCard = useCallback(() => setCard(null), []);

  const [from, to] = compare;
  const bandValues = override?.values ?? layer.v[version]?.[group];
  const before = layer.v[from]?.[group];
  const after = layer.v[to]?.[group];
  const hasDelta = Boolean(before && after);

  // Fark katmanında ölçek simetrik olmalı, yoksa sıfır nötr renge denk gelmez.
  let spread = 1;
  if (mode === "delta" && before && after) {
    let max = 0.01;
    for (let i = 0; i < after.length; i++) max = Math.max(max, Math.abs(after[i] - before[i]));
    spread = max;
  }

  // 120 min obyektin hər render-də yenidən yaradılması deck.gl-i bütün qatı
  // yenidən hesablamağa məcbur edirdi.
  const rows = useMemo(() => layer.h3.map((h3, i) => ({ h3, i })), [layer]);

  // Hüceyrələr yarı şəffafdır: altdakı küçə və sahil xətti görünməsə
  // istifadəçi baxdığı yerin harası olduğunu itirir.
  const colorFor = (i: number): [number, number, number, number] => {
    if (mode === "delta") {
      if (!before || !after) return [148, 163, 184, 60];
      const value = after[i] - before[i];
      if (value === 0) return [148, 163, 184, isBase ? 25 : 70];
      const rgb = mix(FLAT, value < 0 ? DOWN : UP, Math.abs(value) / spread);
      return [rgb[0], rgb[1], rgb[2], 190];
    }
    if (!bandValues) return [148, 163, 184, 60];
    const rgb = sample(BAND_RAMP, (bandValues[i] - 1) / 9);
    return [rgb[0], rgb[1], rgb[2], 178];
  };

  const layers: Layer[] = [
    new H3HexagonLayer({
      id: `cells-r${layer.res}`,
      data: rows,
      pickable: true,
      filled: true,
      // H10-da sərhəd yalnız yaxından çəkilir.
      stroked: !isBase || zoomedIn,
      extruded: false,
      highPrecision: isBase ? false : true,
      getHexagon: (d: { h3: string }) => d.h3,
      getFillColor: (d: { i: number }) => colorFor(d.i),
      getLineColor: theme === "dark" ? [255, 255, 255, 45] : [15, 23, 42, 45],
      lineWidthUnits: "pixels",
      getLineWidth: 1,
      lineWidthMinPixels: 0.5,
      updateTriggers: {
        getFillColor: [group, mode, version, from, to, layer.res, override],
        getLineColor: [theme]
      }
    })
  ];

  for (const poi of pois) {
    if (poi.points.length === 0) continue;
    const rgb = hexToRgb(categoryColor(poi.category));
    const osm = poi.kind === "osm";
    layers.push(
      new ScatterplotLayer({
        id: `poi-${poi.kind}-${poi.category}`,
        data: poi.points,
        pickable: true,
        getPosition: (d: [number, number]) => [d[1], d[0]],
        filled: !osm,
        stroked: true,
        getFillColor: [...rgb, 235],
        getLineColor: osm ? [...rgb, 255] : theme === "dark" ? [15, 23, 42, 220] : [255, 255, 255, 230],
        lineWidthMinPixels: osm ? 2 : 1,
        radiusMinPixels: osm ? 4 : 3,
        radiusMaxPixels: osm ? 8 : 7,
        getRadius: 40
      })
    );
  }

  const describe = useCallback(
    ({ object, layer: hit }: PickingInfo): string | null => {
      if (!object) return null;
      const id = hit?.id ?? "";
      if (id.startsWith("poi-")) {
        const [, kind, ...rest] = id.split("-");
        const name = rest.join("-");
        return (
          `<div style="font-weight:600">${escapeHtml(categoryLabel(name))}</div>
           <div style="opacity:.7">${kind === "osm" ? "OpenStreetMap-dən əlavə" : "iş ortağının verisi"}</div>
           <div style="opacity:.5;margin-top:4px;font-size:10.5px">ətraflı üçün klikləyin</div>`
        );
      }
      const row = object as { h3: string; i: number };
      const shown = mode === "delta" ? to : version;
      const lines = groups
        .map((g) => {
          const now = layer.v[shown]?.[g]?.[row.i];
          if (now === undefined) return "";
          const prev = layer.v[from]?.[g]?.[row.i];
          const delta = mode === "delta" && prev !== undefined ? now - prev : 0;
          const shift =
            Math.abs(delta) < 0.005
              ? ""
              : `<span style="color:${delta < 0 ? "#f87171" : "#4ade80"};margin-left:6px">${
                  delta > 0 ? "+" : ""
                }${fmt(delta)}</span>`;
          const strong = g === group ? "font-weight:700;" : "";
          return `<div style="display:flex;justify-content:space-between;gap:14px;${strong}">
            <span>${escapeHtml(groupLabel(g))}</span>
            <span>${fmt(now)}${shift}</span>
          </div>`;
        })
        .join("");
      const custom =
        override && mode === "band"
          ? `<div style="display:flex;justify-content:space-between;gap:14px;font-weight:700;color:#fdba74;margin-bottom:4px">
              <span>${escapeHtml(override.label)}</span><span>${fmt(override.values[row.i])}</span></div>`
          : "";
      const label =
        mode === "delta"
          ? `${VERSION_LABELS[from]} → ${VERSION_LABELS[to]}`
          : VERSION_LABELS[version];
      return (
        `<div style="font-family:ui-monospace,monospace;font-size:11px;opacity:.65">${escapeHtml(
          row.h3
        )} · H${layer.res}</div>
        <div style="font-size:11px;opacity:.65;margin-bottom:6px">${escapeHtml(label)}${
          isBase ? "" : " · H10 ortalaması"
        }</div>${custom}${lines}${hasDelta || mode !== "delta" ? "" : "<div>müqayisə yoxdur</div>"}`
      );
    },
    [layer, group, mode, version, from, to, groups, isBase, hasDelta, override]
  );

  // deck.gl 9.4-ün öz ipucu qutusu kartın hündürlüyü qədər yuxarıda yerləşirdi;
  // ona görə yalnız xəritənin aşağı hissəsində görünürdü. Qutu burada çəkilir,
  // koordinat birbaşa kətana nisbətdir və kənara çıxanda o biri tərəfə keçir.
  const onHover = useCallback(
    (info: PickingInfo) => {
      const el = tipRef.current;
      if (!el) return;
      const html = info.object ? describe(info) : null;
      if (!html) {
        el.style.display = "none";
        return;
      }
      el.innerHTML = html;
      el.style.display = "block";
      const parent = el.parentElement;
      const pw = parent?.clientWidth ?? 0;
      const ph = parent?.clientHeight ?? 0;
      const w = el.offsetWidth;
      const h = el.offsetHeight;
      let x = info.x + 14;
      let y = info.y + 14;
      if (x + w > pw - 8) x = info.x - w - 14;
      if (y + h > ph - 8) y = info.y - h - 14;
      el.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
    },
    [describe]
  );

  const onClick = useCallback(
    (info: PickingInfo) => {
      const id = info.layer?.id ?? "";
      if (!info.object || !id.startsWith("poi-")) {
        setCard(null);
        return;
      }
      const [, kind, ...rest] = id.split("-");
      const category = rest.join("-");
      const source = pois.find((p) => p.kind === kind && p.category === category);
      const point = info.object as [number, number];
      if (!source) return;
      if (tipRef.current) tipRef.current.style.display = "none";
      setCard({
        key: source.key,
        category,
        index: info.index,
        lat: point[0],
        lon: point[1],
        x: info.x,
        y: info.y
      });
    },
    [pois]
  );

  const container = tipRef.current?.parentElement;

  return (
    <>
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        onHover={onHover}
        onClick={onClick}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "grab")}
        onViewStateChange={({ viewState }) => {
          if (tipRef.current) tipRef.current.style.display = "none";
          if (card) setCard(null);
          const near = (viewState as { zoom: number }).zoom >= EDGE_ZOOM;
          if (near !== zoomedIn) setZoomedIn(near);
        }}
      >
        <Map reuseMaps mapStyle={theme === "dark" ? MAP_STYLE_DARK : MAP_STYLE_LIGHT} />
      </DeckGL>
      <div
        ref={tipRef}
        className="pointer-events-none absolute left-0 top-0 z-20 hidden rounded-lg border border-white/10 bg-[#10161f]/95 p-2.5 text-[12px] text-[#f5f7fb] shadow-lg"
        style={{ minWidth: 200, maxWidth: 280 }}
      />
      {card ? (
        <PoiCard
          target={card}
          bounds={{ width: container?.clientWidth ?? 1200, height: container?.clientHeight ?? 700 }}
          onClose={closeCard}
          onShowInTable={onShowInTable}
        />
      ) : null}
    </>
  );
}

