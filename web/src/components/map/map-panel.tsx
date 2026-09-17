"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { categoryColor, categoryLabel, formatCount, groupLabel, VERSION_LABELS } from "@/lib/data";
import { cn } from "@/lib/utils";
import type { CellLayer, PoiLayers } from "@/types/data";

import type { MapMode, PoiLayer } from "./index-map";

// deck.gl və MapLibre yalnız brauzerdə işləyir; server tərəfdə render olunmur.
const IndexMap = dynamic(() => import("./index-map").then((m) => m.IndexMap), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-[520px] w-full" />
});

const BAND_GRADIENT =
  "linear-gradient(to right, rgb(254,243,199), rgb(253,211,77), rgb(245,158,11), rgb(234,88,12), rgb(214,95,20), rgb(130,43,17))";
const DELTA_GRADIENT =
  "linear-gradient(to right, rgb(214,57,57), rgb(148,163,184), rgb(47,179,68))";

const VERSIONS = ["2025", "2026", "2026osm"] as const;
const COMPARISONS: { key: string; pair: [string, string]; label: string }[] = [
  { key: "data", pair: ["2025", "2026"], label: "2025 → 2026" },
  { key: "osm", pair: ["2026", "2026osm"], label: "OSM təsiri" },
  { key: "all", pair: ["2025", "2026osm"], label: "2025 → 2026+OSM" }
];

type PoiSource = "local" | "osm" | "both";

type Props = {
  layer: CellLayer | null;
  poi: PoiLayers | null;
  groups: string[];
  resolution: number;
  resolutions: number[];
  onResolutionChange: (value: number) => void;
  loading?: boolean;
};

function Segmented<T extends string | number>({
  label,
  options,
  value,
  onChange,
  disabled
}: {
  label: string;
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  disabled?: (value: T) => boolean;
}) {
  return (
    <div className="rounded-md border bg-card/92 p-1.5 backdrop-blur">
      <div className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="flex gap-1">
        {options.map((o) => (
          <button
            key={String(o.value)}
            onClick={() => onChange(o.value)}
            disabled={disabled?.(o.value)}
            className={cn(
              "flex-1 whitespace-nowrap rounded px-1.5 py-1 text-[11px] font-semibold transition-colors disabled:opacity-35",
              o.value === value
                ? "bg-[var(--brand-600)] text-white"
                : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>
    </div>
  );
}

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
  const [version, setVersion] = useState<string>("2026osm");
  const [comparison, setComparison] = useState("osm");
  const [poiCategories, setPoiCategories] = useState<string[]>([]);
  const [poiSource, setPoiSource] = useState<PoiSource>("both");

  const active = groups.includes(group) ? group : (groups[0] ?? "");
  const pair = COMPARISONS.find((c) => c.key === comparison)?.pair ?? ["2026", "2026osm"];
  const available = (v: string) => Boolean(layer?.v[v]?.[active]);

  const togglePoi = (name: string) =>
    setPoiCategories((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );

  const poiNames = poi ? Object.keys(poi["2026"]) : [];

  // Görünən sürüme uyğun POI qatları. 2025 seçiləndə OSM əlavələri göstərilmir.
  const poiLayers = useMemo<PoiLayer[]>(() => {
    if (!poi) return [];
    const base = mode === "band" && version === "2025" ? poi["2025"] : poi["2026"];
    const showOsm = !(mode === "band" && version !== "2026osm");
    const out: PoiLayer[] = [];
    for (const category of poiCategories) {
      if (poiSource !== "osm") {
        out.push({ category, points: base[category] ?? [], kind: "local" });
      }
      if (poiSource !== "local" && showOsm) {
        out.push({ category, points: poi.osm[category] ?? [], kind: "osm" });
      }
    }
    return out;
  }, [poi, poiCategories, poiSource, mode, version]);

  const shownCount = poiLayers.reduce((n, l) => n + l.points.length, 0);

  return (
    <div className="relative h-full min-h-[600px] overflow-hidden rounded-lg">
      {/* Sol üst: seviyye və hüceyrə sayı */}
      <div className="absolute left-3 top-3 z-10 flex flex-wrap items-start gap-1.5">
        <div className="flex items-center gap-1 rounded-md border bg-card/92 p-1 backdrop-blur">
          <span className="px-1 text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
            Səviyyə
          </span>
          {resolutions.map((r) => (
            <button
              key={r}
              onClick={() => onResolutionChange(r)}
              title={r === 10 ? "Hesablamanın aparıldığı səviyyə" : "H10 ballarının ortalaması"}
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
          {layer ? (
            <span className="ml-1.5 text-muted-foreground">
              {layer.res === 10 ? "· hesablama səviyyəsi" : "· H10 ortalaması"}
            </span>
          ) : null}
        </span>
        {loading ? (
          <span className="rounded-md border bg-card/92 px-2 py-1 text-[11px] backdrop-blur">
            yüklənir…
          </span>
        ) : null}
        {shownCount > 0 ? (
          <span className="rounded-md border bg-card/92 px-2 py-1 text-[11px] tabular-nums backdrop-blur">
            {formatCount(shownCount)} obyekt
          </span>
        ) : null}
      </div>

      {/* Sağ üst: idarə paneli */}
      <div className="absolute bottom-14 right-3 top-3 z-10 w-[236px] space-y-1.5 overflow-y-auto pr-0.5">
        <Segmented
          label="Rejim"
          value={mode}
          onChange={setMode}
          options={[
            { value: "band", label: "Bal" },
            { value: "delta", label: "Dəyişim" }
          ]}
        />

        {mode === "band" ? (
          <Segmented
            label="Veri sürümü"
            value={version}
            onChange={setVersion}
            disabled={(v) => !available(v)}
            options={VERSIONS.map((v) => ({
              value: v,
              label: v === "2026osm" ? "2026+OSM" : v
            }))}
          />
        ) : (
          <div className="rounded-md border bg-card/92 p-1.5 backdrop-blur">
            <div className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Müqayisə
            </div>
            <div className="grid gap-1">
              {COMPARISONS.map((c) => (
                <button
                  key={c.key}
                  onClick={() => setComparison(c.key)}
                  disabled={!available(c.pair[0]) || !available(c.pair[1])}
                  className={cn(
                    "rounded px-2 py-1 text-left text-[11px] font-semibold transition-colors disabled:opacity-35",
                    c.key === comparison
                      ? "bg-[var(--brand-600)] text-white"
                      : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
                  )}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="rounded-md border bg-card/92 p-1.5 backdrop-blur">
          <div className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
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

        {poiNames.length > 0 ? (
          <div className="rounded-md border bg-card/92 p-1.5 backdrop-blur">
            <div className="flex items-center justify-between px-1 pb-1">
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                Obyektlər {poiCategories.length > 0 ? `(${poiCategories.length})` : ""}
              </span>
              {poiCategories.length > 0 ? (
                <button
                  onClick={() => setPoiCategories([])}
                  className="text-[10px] text-muted-foreground hover:text-foreground"
                >
                  təmizlə
                </button>
              ) : null}
            </div>
            <div className="mb-1.5 flex gap-1">
              {(
                [
                  ["both", "Hamısı"],
                  ["local", "Yerli ●"],
                  ["osm", "OSM ○"]
                ] as [PoiSource, string][]
              ).map(([value, label]) => (
                <button
                  key={value}
                  onClick={() => setPoiSource(value)}
                  className={cn(
                    "flex-1 rounded px-1 py-0.5 text-[10.5px] font-medium",
                    poiSource === value
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:bg-muted/60"
                  )}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-2 gap-1">
              {poiNames.map((name) => {
                const on = poiCategories.includes(name);
                const added = poi?.osm[name]?.length ?? 0;
                return (
                  <button
                    key={name}
                    onClick={() => togglePoi(name)}
                    title={added ? `OSM-dən +${added}` : undefined}
                    className={cn(
                      "flex items-center gap-1.5 truncate rounded border px-1.5 py-1 text-left text-[10.5px] font-medium transition-colors",
                      on ? "border-foreground/40 bg-muted text-foreground" : "border-transparent text-muted-foreground hover:bg-muted/60"
                    )}
                  >
                    <span
                      className="h-2.5 w-2.5 flex-shrink-0 rounded-full"
                      style={{ background: categoryColor(name) }}
                    />
                    <span className="truncate">{categoryLabel(name)}</span>
                  </button>
                );
              })}
            </div>
          </div>
        ) : null}
      </div>

      {/* Sol alt: efsanə */}
      <div className="absolute bottom-3 left-3 z-10 flex flex-wrap items-center gap-2 rounded-md border bg-card/92 px-2.5 py-1.5 backdrop-blur">
        <span className="text-[10.5px] font-semibold">
          {mode === "delta"
            ? `${VERSION_LABELS[pair[0]]} → ${VERSION_LABELS[pair[1]]}`
            : VERSION_LABELS[version]}
        </span>
        <span className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
          {mode === "delta" ? "Aşağı" : "1"}
        </span>
        <div
          className="h-2 w-32 rounded-full"
          style={{ background: mode === "delta" ? DELTA_GRADIENT : BAND_GRADIENT }}
        />
        <span className="text-[10.5px] font-medium uppercase tracking-wider text-muted-foreground">
          {mode === "delta" ? "Yuxarı" : "10"}
        </span>
        {poiCategories.length > 0 ? (
          <span className="ml-1 border-l pl-2 text-[10.5px] text-muted-foreground">
            ● iş ortağı · ○ OSM əlavəsi
          </span>
        ) : null}
      </div>

      {layer ? (
        <IndexMap
          layer={layer}
          group={active}
          mode={mode}
          version={version}
          compare={pair}
          pois={poiLayers}
          groups={groups}
        />
      ) : (
        <Skeleton className="h-full min-h-[600px] w-full" />
      )}
    </div>
  );
}
