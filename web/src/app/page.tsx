"use client";

import { useCallback, useEffect, useState } from "react";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { NavSidebar, type View } from "@/components/dashboard/nav-sidebar";
import { TopBar } from "@/components/dashboard/top-bar";
import { MapPanel } from "@/components/map/map-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { ApiView } from "@/components/views/api";
import { ChangeView } from "@/components/views/change";
import { EnrichmentView } from "@/components/views/enrichment";
import { H10View } from "@/components/views/h10";
import { IndicesView } from "@/components/views/indices";
import { MetroView } from "@/components/views/metro";
import { OverviewView } from "@/components/views/overview";
import { ProposalsView } from "@/components/views/proposals";
import { ValidationView } from "@/components/views/validation";
import { formatCount, loadCells, loadPoi, loadSummary } from "@/lib/data";
import type { CellLayer, PoiLayers, Summary } from "@/types/data";

/** Yan panelin daraldılmış halı yenidən yüklənəndə də qalsın. */
const RAIL_KEY = "urbangeoai-rail-collapsed";

const TITLES: Record<View, { title: string; subtitle: string }> = {
  overview: {
    title: "İcmal",
    subtitle: "Izgara, POI və indekslərin ümumi vəziyyəti"
  },
  map: {
    title: "Xəritə",
    subtitle: "H3 hüceyrələri üzərində əlçatanlıq balı, POI qatı və iki sürüm arasındakı fərq"
  },
  enrichment: {
    title: "OSM zənginləşdirmə",
    subtitle: "Yerli hovuzda olmayan obyektlər OpenStreetMap-dən tapılıb əlavə edildi"
  },
  h10: {
    title: "H10 yoxlaması",
    subtitle: "Hesablama həqiqətən H10-da aparılırmı və hamısı tamdırmı"
  },
  api: {
    title: "API",
    subtitle: "Bu sistemi başqa sistemlərə bağlayan xidmət"
  },
  indices: {
    title: "İndekslər",
    subtitle: "Bileşen yükleri, bant doluluğu, indekslər arası korelyasiya və kalibrasyon önceliği"
  },
  metro: {
    title: "Metro",
    subtitle: "OpenStreetMap düyünlərinin təmizlənməsi — hər qərarın səbəbi ilə"
  },
  validation: {
    title: "Veri denetimi",
    subtitle: "Ham fayllar üzərində doqquz müstəqil yoxlama"
  },
  change: {
    title: "Dəyişim",
    subtitle: "Veri etkisinin yöntem etkisindən ayrılması"
  },
  proposals: {
    title: "Təkliflər",
    subtitle: "Qərar bekleyen maddələr — iş ortağına verilir"
  }
};

export default function Page() {
  const [view, setView] = useState<View>("overview");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [poi, setPoi] = useState<PoiLayers | null>(null);
  const [resolution, setResolution] = useState(9);
  const [layers, setLayers] = useState<Record<number, CellLayer>>({});
  const [loadingLayer, setLoadingLayer] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      const [s, p] = await Promise.all([loadSummary(), loadPoi()]);
      if (cancelled) return;
      if (!s) {
        setFailed(true);
        return;
      }
      setSummary(s);
      setPoi(p);
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Harita katmanı ancaq xəritə açılanda çəkilir — H9 1 MB-dan böyükdür və
  // icmal səhifəsi üçün lazım deyil.
  useEffect(() => {
    if (view !== "map" || layers[resolution]) return;
    let cancelled = false;
    setLoadingLayer(true);
    void (async () => {
      const layer = await loadCells(resolution);
      if (cancelled) return;
      if (layer) setLayers((prev) => ({ ...prev, [resolution]: layer }));
      setLoadingLayer(false);
    })();
    return () => {
      cancelled = true;
    };
  }, [view, resolution, layers]);

  const [railCollapsed, setRailCollapsed] = useState(false);
  useEffect(() => {
    try {
      setRailCollapsed(window.localStorage.getItem(RAIL_KEY) === "1");
    } catch {
      /* gizli rejim — açıq başlasın */
    }
  }, []);
  const toggleRail = useCallback(() => {
    setRailCollapsed((prev) => {
      const next = !prev;
      try {
        window.localStorage.setItem(RAIL_KEY, next ? "1" : "0");
      } catch {
        /* kvota xətası — əhəmiyyətsiz */
      }
      return next;
    });
  }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "b" || !(e.ctrlKey || e.metaKey) || e.altKey) return;
      const el = document.activeElement;
      if (el && ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)) return;
      e.preventDefault();
      toggleRail();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggleRail]);

  const heading = TITLES[view];

  return (
    <main className="min-h-screen bg-background lg:h-screen lg:overflow-hidden">
      <div
        className={
          "grid min-h-screen grid-cols-1 lg:h-screen " +
          (railCollapsed ? "lg:grid-cols-[68px_1fr]" : "lg:grid-cols-[248px_1fr]")
        }
      >
        <aside className="border-b bg-card/40 lg:h-screen lg:overflow-y-auto lg:border-b-0 lg:border-r">
          <NavSidebar
            active={view}
            onChange={setView}
            collapsed={railCollapsed}
            onToggleCollapsed={toggleRail}
            badges={
              summary
                ? {
                    metro: String(summary.metro.nodes.length),
                    validation: String(summary.validation.length),
                    indices: String(summary.meta.indices),
                    enrichment: `+${summary.meta.poiOsm}`,
                    h10: summary.h10?.all_ok ? "✓" : ""
                  }
                : undefined
            }
          />
        </aside>

        <section className="flex min-w-0 flex-col lg:h-screen lg:overflow-hidden">
          <TopBar title={heading.title} subtitle={heading.subtitle}>
            {summary ? (
              <span className="hidden flex-shrink-0 rounded-md border px-2.5 py-1 text-[11px] tabular-nums text-muted-foreground md:inline">
                {formatCount(summary.meta.cells)} H10 hüceyrə · {formatCount(summary.meta.poi)} obyekt
                (OSM +{formatCount(summary.meta.poiOsm)})
              </span>
            ) : null}
          </TopBar>

          <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-5">
            {failed ? (
              <DashboardCard title="Veri tapılmadı" subtitle="public/data altında JSON yoxdur">
                <p className="text-[12px] leading-relaxed text-muted-foreground">
                  Panel boru hattının çıxışını oxuyur. Əvvəlcə{" "}
                  <span className="font-mono">python scripts/build_web_data.py</span> işlədilməlidir.
                </p>
              </DashboardCard>
            ) : !summary ? (
              <>
                <Skeleton className="h-24 w-full" />
                <Skeleton className="h-96 w-full" />
              </>
            ) : view === "overview" ? (
              <OverviewView summary={summary} />
            ) : view === "map" ? (
              <DashboardCard
                title="Əlçatanlıq xəritəsi"
                subtitle="Hesablama H10-da; H7–H9 onun ortalaması. Sürüm seçərək 2025, 2026 və OSM əlavəsindən sonrakı vəziyyəti müqayisə edin"
                bodyClassName="p-0"
                className="min-h-[680px] flex-1"
              >
                <MapPanel
                  layer={layers[resolution] ?? null}
                  poi={poi}
                  groups={summary.groups}
                  resolution={resolution}
                  resolutions={summary.meta.mapResolutions}
                  onResolutionChange={setResolution}
                  loading={loadingLayer}
                />
              </DashboardCard>
            ) : view === "enrichment" ? (
              <EnrichmentView summary={summary} />
            ) : view === "h10" ? (
              <H10View summary={summary} />
            ) : view === "api" ? (
              <ApiView />
            ) : view === "indices" ? (
              <IndicesView summary={summary} />
            ) : view === "metro" ? (
              <MetroView summary={summary} />
            ) : view === "validation" ? (
              <ValidationView summary={summary} />
            ) : view === "change" ? (
              <ChangeView summary={summary} />
            ) : (
              <ProposalsView summary={summary} />
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
