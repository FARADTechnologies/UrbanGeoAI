"use client";

import type { Layer } from "@deck.gl/core";
import { H3HexagonLayer } from "@deck.gl/geo-layers";
import { ScatterplotLayer } from "@deck.gl/layers";
import DeckGL from "@deck.gl/react";
import Map from "react-map-gl/maplibre";

import { useTheme } from "@/components/theme-provider";
import { categoryLabel, groupLabel } from "@/lib/data";
import type { CellLayer, PoiLayers } from "@/types/data";

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

export type MapMode = "band" | "delta";

type Props = {
  layer: CellLayer;
  poi: PoiLayers | null;
  /** Renklendirilen indeks grubu. */
  group: string;
  mode: MapMode;
  /** Üzerine nokta olarak çizilen POI kategorileri. */
  poiCategories: string[];
  /** Bütün gruplar — ipucu kartı hepsini gösterir. */
  groups: string[];
};

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

export function IndexMap({ layer, poi, group, mode, poiCategories, groups }: Props) {
  const { theme } = useTheme();
  const values = mode === "delta" ? layer.deltas[group] : layer.indices[group];
  const hasValues = Array.isArray(values);

  // Hüceyrələr yarı şəffafdır: altdakı küçə və sahil xətti görünməsə
  // istifadəçi baxdığı yerin harası olduğunu itirir.
  // Fark katmanında ölçek simetrik olmalı, yoksa sıfır nötr renge denk gelmez.
  const spread = hasValues ? Math.max(...values.map((v) => Math.abs(v)), 0.01) : 1;

  const rows = layer.h3.map((h3, i) => ({ h3, i }));

  const colorFor = (i: number): [number, number, number, number] => {
    if (!hasValues) return [148, 163, 184, 120];
    const value = values[i];
    if (mode === "delta") {
      const ratio = Math.abs(value) / spread;
      const rgb = mix(FLAT, value < 0 ? DOWN : UP, ratio);
      return [rgb[0], rgb[1], rgb[2], 185];
    }
    const rgb = sample(BAND_RAMP, (value - 1) / 9);
    return [rgb[0], rgb[1], rgb[2], 178];
  };

  const layers: Layer[] = [
    new H3HexagonLayer({
      id: `cells-r${layer.res}-${group}-${mode}`,
      data: rows,
      pickable: true,
      filled: true,
      stroked: true,
      extruded: false,
      highPrecision: true,
      getHexagon: (d: { h3: string }) => d.h3,
      getFillColor: (d: { i: number }) => colorFor(d.i),
      getLineColor: theme === "dark" ? [255, 255, 255, 40] : [15, 23, 42, 30],
      lineWidthMinPixels: 0.5,
      updateTriggers: { getFillColor: [group, mode, layer.res] }
    })
  ];

  // POI katmanları hücrelerin üstünde; her kategori kendi rengiyle.
  poiCategories.forEach((name, order) => {
    const points = poi?.[name];
    if (!points || points.length === 0) return;
    const hue = (order * 67) % 360;
    layers.push(
      new ScatterplotLayer({
        id: `poi-${name}`,
        data: points,
        pickable: true,
        getPosition: (d: [number, number]) => [d[1], d[0]],
        getFillColor: hslToRgb(hue, 0.72, theme === "dark" ? 0.66 : 0.42),
        getLineColor: theme === "dark" ? [15, 23, 42, 220] : [255, 255, 255, 230],
        lineWidthMinPixels: 1,
        stroked: true,
        radiusMinPixels: 3,
        radiusMaxPixels: 7,
        getRadius: 40
      })
    );
  });

  return (
    <DeckGL
      initialViewState={INITIAL_VIEW_STATE}
      controller
      layers={layers}
      getTooltip={({ object, layer: hit }) => {
        if (!object) return null;
        if (hit?.id?.startsWith("poi-")) {
          const name = hit.id.slice(4);
          return tooltipCard(`<div style="font-weight:600">${escapeHtml(categoryLabel(name))}</div>`);
        }
        const row = object as { h3: string; i: number };
        const lines = groups
          .map((g) => {
            const band = layer.indices[g]?.[row.i];
            if (band === undefined) return "";
            const delta = layer.deltas[g]?.[row.i];
            const shift =
              delta === undefined || Math.abs(delta) < 0.005
                ? ""
                : `<span style="color:${delta < 0 ? "#f87171" : "#4ade80"};margin-left:6px">${
                    delta > 0 ? "+" : ""
                  }${delta.toFixed(2)}</span>`;
            const strong = g === group ? "font-weight:700;" : "";
            return `<div style="display:flex;justify-content:space-between;gap:14px;${strong}">
              <span>${escapeHtml(groupLabel(g))}</span>
              <span>${band.toFixed(2)}${shift}</span>
            </div>`;
          })
          .join("");
        return tooltipCard(
          `<div style="font-family:ui-monospace,monospace;font-size:11px;opacity:.65;margin-bottom:6px">${escapeHtml(
            row.h3
          )}</div>${lines}`
        );
      }}
    >
      <Map reuseMaps mapStyle={theme === "dark" ? MAP_STYLE_DARK : MAP_STYLE_LIGHT} />
    </DeckGL>
  );
}

function tooltipCard(html: string) {
  return {
    html: `<div style="min-width:190px">${html}</div>`,
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

function hslToRgb(h: number, s: number, l: number): RGB {
  const k = (n: number) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n: number) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(f(0) * 255), Math.round(f(8) * 255), Math.round(f(4) * 255)];
}

/** Efsanenin gösterdiği degrade — harita rampasıyla aynı duruyor. */
export const BAND_GRADIENT = BAND_RAMP.map((c) => `rgb(${c.join(",")})`).join(", ");
