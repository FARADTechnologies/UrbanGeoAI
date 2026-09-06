"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { categoryLabel, formatCount, groupLabel } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { CellLayer, PoiLayers } from "@/types/data";

import type { MapMode } from "./index-map";

// deck.gl və MapLibre yalnız brauzerdə işləyir; server tərəfdə render olunmur.
const IndexMap = dynamic(() => import("./index-map").then((m) => m.IndexMap), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-[520px] w-full" />
});

const BAND_GRADIENT =
  "linear-gradient(to right, rgb(254,243,199), rgb(253,211,77), rgb(245,158,11), rgb(234,88,12), rgb(214,95,20), rgb(130,43,17))";
const DELTA_GRADIENT =
  "linear-gradient(to right, rgb(214,57,57), rgb(148,163,184), rgb(47,179,68))";

type Props = {
  layer: CellLayer | null;
  poi: PoiLayers | null;
  groups: string[];
  resolution: number;
  resolutions: number[];
  onResolutionChange: (value: number) => void;
  loading?: boolean;
};

export function MapPanel({
  layer,
  poi,
  groups,
  resolution,
  resolutions,
  onResolutionChange,
  loading
}: Props) {
  const [group, setGroup] = useState(groups[0] ?? "");
  const [mode, setMode] = useState<MapMode>("band");
  const [poiCategories, setPoiCategories] = useState<string[]>([]);

  const active = groups.includes(group) ? group : (groups[0] ?? "");
  const hasDelta = Boolean(layer?.deltas?.[active]);
  const shownMode: MapMode = mode === "delta" && !hasDelta ? "band" : mode;

  const togglePoi = (name: string) =>
    setPoiCategories((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );

  const poiNames = poi ? Object.keys(poi) : [];

  return (
    <div className="relative h-full min-h-[560px] overflow-hidden rounded-lg">
      {/* Sol üst: seviyye və hüceyrə sayı */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-center gap-1.5">
        <div className="flex items-center gap-1 rounded-md border bg-card/92 p-1 backdrop-blur">
          <span className="px-1 text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
            Səviyyə
          </span>
          {resolutions.map((r) => (
            <button
              key={r}
              onClick={() => onResolutionChange(r)}
              className={cn(
                "rounded px-2 py-0.5 text-[11px] font-semibold transition-colors",
                r === resolution
                  ? "bg-[var(--brand-600)] text-white"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              H{r}
            </button>
          ))}
        </div>
        <span className="rounded-md border bg-card/92 px-2 py-1 text-[11px] font-medium tabular-nums backdrop-blur">
          {layer ? `${formatCount(layer.h3.length)} hüceyrə` : "yüklənir…"}
        </span>
        {loading ? (
          <span className="rounded-md border bg-card/92 px-2 py-1 text-[11px] backdrop-blur">
            yüklənir…
          </span>
        ) : null}
      </div>

      {/* Sağ üst: indeks və rejim */}
      <div className="absolute right-3 top-3 z-10 w-[214px] space-y-1.5">
        <div className="rounded-md border bg-card/92 p-1.5 backdrop-blur">
          <div className="px-1 pb-1 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
            İndeks
          </div>
          <div className="grid grid-cols-2 gap-1">
            {groups.map((g) => (
              <button
                key={g}
                onClick={() => setGroup(g)}
                className={cn(
                  "truncate rounded px-1.5 py-1 text-[11px] font-medium transition-colors",
                  g === active
                    ? "bg-[var(--brand-600)] text-white"
                    : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                )}
              >
                {groupLabel(g)}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-1 rounded-md border bg-card/92 p-1 backdrop-blur">
          <button
            onClick={() => setMode("band")}
            className={cn(
              "flex-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors",
              shownMode === "band"
                ? "bg-[var(--brand-600)] text-white"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Bal
          </button>
          <button
            onClick={() => setMode("delta")}
            disabled={!hasDelta}
            title={hasDelta ? undefined : "Bu indeksin əvvəlki sürümdə qarşılığı yoxdur"}
            className={cn(
              "flex-1 rounded px-2 py-0.5 text-[11px] font-medium transition-colors disabled:opacity-40",
              shownMode === "delta"
                ? "bg-[var(--brand-600)] text-white"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            Dəyişim
          </button>
        </div>

        {poiNames.length > 0 ? (
          <details className="rounded-md border bg-card/92 backdrop-blur">
            <summary className="cursor-pointer select-none px-2.5 py-1.5 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
              POI qatı {poiCategories.length > 0 ? `(${poiCategories.length})` : ""}
            </summary>
            <div className="max-h-56 overflow-y-auto px-1.5 pb-1.5">
              <div className="grid grid-cols-2 gap-1">
                {poiNames.map((name) => (
                  <button
                    key={name}
                    onClick={() => togglePoi(name)}
                    className={cn(
                      "truncate rounded px-1.5 py-1 text-left text-[10.5px] font-medium transition-colors",
                      poiCategories.includes(name)
                        ? "bg-[var(--brand-600)] text-white"
                        : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                    )}
                  >
                    {categoryLabel(name)}
                  </button>
                ))}
              </div>
            </div>
          </details>
        ) : null}
      </div>

      {/* Sol alt: efsanə */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 rounded-md border bg-card/92 px-2.5 py-1.5 backdrop-blur">
        <span className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
          {shownMode === "delta" ? "Aşağı" : "Aşağı bal"}
        </span>
        <div
          className="h-2 w-32 rounded-full"
          style={{ background: shownMode === "delta" ? DELTA_GRADIENT : BAND_GRADIENT }}
        />
        <span className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
          {shownMode === "delta" ? "Yuxarı" : "Yüksək bal"}
        </span>
      </div>

      {layer ? (
        <IndexMap
          layer={layer}
          poi={poi}
          group={active}
          mode={shownMode}
          poiCategories={poiCategories}
          groups={groups}
        />
      ) : (
        <Skeleton className="h-full min-h-[560px] w-full" />
      )}
    </div>
  );
}
