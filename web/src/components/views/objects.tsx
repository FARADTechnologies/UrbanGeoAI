"use client";

import { Download, ExternalLink, Search } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  categoryColor,
  categoryLabel,
  formatCount,
  googleMapsUrl,
  loadPoiInfo,
  osmUrl,
  safeUrl
} from "@/lib/data";
import type { PoiDetail, PoiInfo, PoiKey, PoiLayers, PoiSelection } from "@/types/data";

type Dataset = "2026" | "2025";

type Row = {
  key: PoiKey;
  category: string;
  index: number;
  lat: number;
  lon: number;
  d: PoiDetail;
};

const PAGE = 50;

function sourceLabel(row: Row) {
  if (row.key === "osm") return "OSM";
  if (row.category === "metro") return "OSM · metro";
  return "İş ortağı";
}

function rowsOf(poi: PoiLayers, info: PoiInfo, dataset: Dataset): Row[] {
  const keys: PoiKey[] = dataset === "2025" ? ["2025"] : ["2026", "osm"];
  const out: Row[] = [];
  for (const key of keys) {
    for (const [category, points] of Object.entries(poi[key] ?? {})) {
      const details = info[key]?.[category] ?? [];
      points.forEach(([lat, lon], index) =>
        out.push({ key, category, index, lat, lon, d: details[index] ?? {} })
      );
    }
  }
  return out;
}

function csvCell(value: string | number | undefined) {
  const text = value === undefined ? "" : String(value);
  return /[",\n;]/.test(text) ? `"${text.replaceAll('"', '""')}"` : text;
}

function download(rows: Row[], dataset: Dataset) {
  const header = [
    "category", "category_label", "name", "name_original", "source", "lat", "lon",
    "address", "website", "phone", "opening_hours", "osm", "google_maps"
  ];  // prettier-ignore
  const lines = rows.map((r) =>
    [
      r.category,
      categoryLabel(r.category),
      r.d.n,
      r.d.o,
      sourceLabel(r),
      r.lat,
      r.lon,
      r.d.addr,
      safeUrl(r.d.web) ?? "",
      r.d.phone,
      r.d.hours,
      osmUrl(r.d.id) ?? "",
      googleMapsUrl(r.lat, r.lon)
    ]
      .map(csvCell)
      .join(",")
  );
  // BOM: Excel UTF-8-i yalnız bununla tanıyır (ə, ş, ğ pozulmasın).
  const blob = new Blob(["﻿" + [header.join(","), ...lines].join("\n")], {
    type: "text/csv;charset=utf-8"
  });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `urbangeoai-obyektler-${dataset === "2025" ? "2025" : "2026-osm"}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ObjectsView({ poi, focus }: { poi: PoiLayers | null; focus: PoiSelection | null }) {
  const [info, setInfo] = useState<PoiInfo | null>(null);
  const [dataset, setDataset] = useState<Dataset>(focus?.key === "2025" ? "2025" : "2026");
  const [category, setCategory] = useState<string>(focus?.category ?? "");
  const [source, setSource] = useState<"" | "local" | "osm">("");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const highlightRef = useRef<HTMLTableRowElement>(null);

  useEffect(() => {
    void loadPoiInfo().then(setInfo);
  }, []);

  // Xəritədən gələndə: həmin kateqoriya, filtrlər təmiz.
  useEffect(() => {
    if (!focus) return;
    setDataset(focus.key === "2025" ? "2025" : "2026");
    setCategory(focus.category);
    setSource("");
    setQuery("");
  }, [focus]);

  const all = useMemo(() => (poi && info ? rowsOf(poi, info, dataset) : []), [poi, info, dataset]);
  const categories = useMemo(() => [...new Set(all.map((r) => r.category))], [all]);

  const filtered = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("az");
    return all.filter(
      (r) =>
        (!category || r.category === category) &&
        (!source || (source === "osm" ? r.key === "osm" : r.key !== "osm")) &&
        (!q ||
          (r.d.n ?? "").toLocaleLowerCase("az").includes(q) ||
          (r.d.o ?? "").toLocaleLowerCase("az").includes(q) ||
          (r.d.addr ?? "").toLocaleLowerCase("az").includes(q))
    );
  }, [all, category, source, query]);

  const focusIndex = useMemo(
    () =>
      focus
        ? filtered.findIndex(
            (r) => r.key === focus.key && r.category === focus.category && r.index === focus.index
          )
        : -1,
    [filtered, focus]
  );

  useEffect(() => {
    setPage(focusIndex >= 0 ? Math.floor(focusIndex / PAGE) : 0);
  }, [focusIndex, category, source, query, dataset]);

  useEffect(() => {
    highlightRef.current?.scrollIntoView({ block: "center", behavior: "smooth" });
  }, [page, focusIndex]);

  if (!poi || !info) {
    return <Skeleton className="h-[600px] w-full" />;
  }

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const shown = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const select =
    "h-8 rounded-md border bg-background px-2 text-[12px] focus:outline-none focus:ring-1 focus:ring-[var(--brand-500)]";

  return (
    <DashboardCard
      title="Obyekt cədvəli"
      subtitle={`${formatCount(filtered.length)} / ${formatCount(all.length)} obyekt · xəritədəki nöqtələrin hamısı, hesablamaya girən hovuz`}
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <select className={select} value={dataset} onChange={(e) => setDataset(e.target.value as Dataset)}>
          <option value="2026">2026 + OSM</option>
          <option value="2025">2025</option>
        </select>
        <select className={select} value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">Bütün kateqoriyalar</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
        {dataset === "2026" ? (
          <select className={select} value={source} onChange={(e) => setSource(e.target.value as typeof source)}>
            <option value="">Hər iki mənbə</option>
            <option value="local">İş ortağı</option>
            <option value="osm">OSM əlavəsi</option>
          </select>
        ) : null}
        <label className="relative flex-1">
          <Search className="pointer-events-none absolute left-2 top-2 h-4 w-4 text-muted-foreground" />
          <input
            className={`${select} w-full min-w-[180px] pl-8`}
            placeholder="Ad və ya ünvan axtar…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </label>
        <button
          type="button"
          onClick={() => download(filtered, dataset)}
          className="flex h-8 items-center gap-1.5 rounded-md bg-[var(--brand-600)] px-3 text-[12px] font-semibold text-white hover:opacity-90"
        >
          <Download className="h-3.5 w-3.5" /> CSV yüklə
        </button>
      </div>

      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full min-w-[860px] border-separate border-spacing-0 text-[12px]">
          <thead className="bg-muted/40">
            <tr>
              {["Kateqoriya", "Ad", "Mənbə", "Koordinat", "Ünvan / məlumat", ""].map((h) => (
                <th
                  key={h}
                  className="border-b px-3 py-2 text-left text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const hit = page * PAGE + i === focusIndex;
              const web = safeUrl(r.d.web);
              return (
                <tr
                  key={`${r.key}-${r.category}-${r.index}`}
                  ref={hit ? highlightRef : undefined}
                  className={hit ? "bg-[var(--brand-500)]/15 outline outline-2 -outline-offset-2 outline-[var(--brand-500)]" : "hover:bg-muted/30"}
                >
                  <td className="border-b px-3 py-1.5">
                    <span className="flex items-center gap-1.5">
                      <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ background: categoryColor(r.category) }} />
                      {categoryLabel(r.category)}
                    </span>
                  </td>
                  <td className="border-b px-3 py-1.5">
                    <div className="font-medium">{r.d.n || <span className="text-muted-foreground">adsız</span>}</div>
                    {r.d.o ? <div className="text-[10.5px] text-muted-foreground">orijinal: {r.d.o}</div> : null}
                  </td>
                  <td className="border-b px-3 py-1.5 text-muted-foreground">{sourceLabel(r)}</td>
                  <td className="border-b px-3 py-1.5 font-mono text-[11px] tabular-nums">
                    {r.lat.toFixed(5)}, {r.lon.toFixed(5)}
                  </td>
                  <td className="border-b px-3 py-1.5 text-[11.5px]">
                    {[r.d.addr, r.d.phone, r.d.hours].filter(Boolean).join(" · ")}
                    {web ? (
                      <>
                        {" "}
                        <a href={web} target="_blank" rel="noopener noreferrer" className="text-[var(--brand-600)] hover:underline">
                          sayt
                        </a>
                      </>
                    ) : null}
                  </td>
                  <td className="border-b px-3 py-1.5 text-right">
                    <a
                      href={googleMapsUrl(r.lat, r.lon)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] hover:bg-muted/50"
                    >
                      <ExternalLink className="h-3 w-3" /> Maps
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="mt-3 flex items-center justify-between text-[12px] text-muted-foreground">
        <span>
          Səhifə {page + 1} / {pages}
        </span>
        <div className="flex gap-1.5">
          <button
            type="button"
            disabled={page === 0}
            onClick={() => setPage((p) => p - 1)}
            className="rounded-md border px-2.5 py-1 disabled:opacity-40"
          >
            ← Əvvəlki
          </button>
          <button
            type="button"
            disabled={page >= pages - 1}
            onClick={() => setPage((p) => p + 1)}
            className="rounded-md border px-2.5 py-1 disabled:opacity-40"
          >
            Növbəti →
          </button>
        </div>
      </div>
    </DashboardCard>
  );
}
