"use client";

import type { Layer } from "@deck.gl/core";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import Map from "react-map-gl/maplibre";

import { useTheme } from "@/components/theme-provider";
import { categoryColor, categoryLabel, groupLabel, VERSION_LABELS } from "@/lib/data";
import type { CellLayer, Points } from "@/types/data";

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

export function IndexMap({ layer, group, mode, version, compare, pois, groups }: Props) {
  const { theme } = useTheme();
  const isBase = layer.res >= 10;

  const [from, to] = compare;
  const bandValues = layer.v[version]?.[group];
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

  const rows = layer.h3.map((h3, i) => ({ h3, i }));

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
      // H10'da 120 bin sınır çizgisi haritayı boğar ve yavaşlatır.
      stroked: !isBase,
      extruded: false,
      highPrecision: isBase ? false : true,
      getHexagon: (d: { h3: string }) => d.h3,
      getFillColor: (d: { i: number }) => colorFor(d.i),
      getLineColor: theme === "dark" ? [255, 255, 255, 40] : [15, 23, 42, 30],
      lineWidthMinPixels: 0.5,
      updateTriggers: { getFillColor: [group, mode, version, from, to, layer.res] }
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

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW_STATE}
      controller
      layers={layers}
      getTooltip={({ object, layer: hit }) => {
        if (!object) return null;
        const id = hit?.id ?? "";
        if (id.startsWith("poi-")) {
          const [, kind, ...rest] = id.split("-");
          const name = rest.join("-");
          return tooltipCard(
            `<div style="font-weight:600">${escapeHtml(categoryLabel(name))}</div>
             <div style="opacity:.7">${kind === "osm" ? "OpenStreetMap-dən əlavə" : "iş ortağının verisi"}</div>`
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
        const label =
          mode === "delta"
            ? `${VERSION_LABELS[from]} → ${VERSION_LABELS[to]}`
            : VERSION_LABELS[version];
        return tooltipCard(
          `<div style="font-family:ui-monospace,monospace;font-size:11px;opacity:.65">${escapeHtml(
            row.h3
          )} · H${layer.res}</div>
          <div style="font-size:11px;opacity:.65;margin-bottom:6px">${escapeHtml(label)}${
            isBase ? "" : " · H10 ortalaması"
          }</div>${lines}${hasDelta || mode !== "delta" ? "" : "<div>müqayisə yoxdur</div>"}`
        );
      }}
    >
      <Map reuseMaps mapStyle={theme === "dark" ? MAP_STYLE_DARK : MAP_STYLE_LIGHT} />
    </DeckGL>
  );
}

function tooltipCard(html: string) {
  return {
    html: `<div style="min-width:200px">${html}</div>`,
    style: {
      backgroundColor: "rgba(16, 22, 31, 0.96)",
      border: "1px solid rgba(255,255,255,0.12)",
      borderRadius: "8px",
      color: "#f5f7fb",
      fontSize: "12px",
      padding: "10px"
    }
  };
}
