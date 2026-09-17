"use client";

import { useEffect, useState } from "react";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { API_URL } from "@/lib/data";
import { cn } from "@/lib/utils";

type Endpoint = {
  method: "GET" | "POST";
  path: string;
  what: string;
  example: string;
};

const ENDPOINTS: Endpoint[] = [
  { method: "GET", path: "/health", what: "Xidmət işləyirmi, neçə hüceyrə yükləndi", example: "/health" },
  { method: "GET", path: "/v1/meta", what: "İndekslər, səviyyələr, model və POI sayları", example: "/v1/meta" },
  {
    method: "GET",
    path: "/v1/point?lat=&lon=",
    what: "Bir koordinatın düşdüyü H10 hüceyrəsinin 7 balı, xam indeksi və məsafələri",
    example: "/v1/point?lat=40.3777&lon=49.8520"
  },
  {
    method: "GET",
    path: "/v1/cells/{h3}",
    what: "H10 birbaşa; H6–H9 verilsə içindəki H10-ların ortalaması",
    example: "/v1/cells/882ce58189fffff"
  },
  {
    method: "POST",
    path: "/v1/points",
    what: "Bir sorğuda 1000-ə qədər nöqtə — elanlar siyahısı üçün",
    example: '{"points":[{"id":"elan-1","lat":40.3777,"lon":49.852}]}'
  },
  {
    method: "GET",
    path: "/v1/poi/nearby?lat=&lon=&radius_m=",
    what: "Ətrafdakı obyektlər məsafə ilə; mənbə (yerli/osm) yazılır",
    example: "/v1/poi/nearby?lat=40.3777&lon=49.852&radius_m=500&category=coffee"
  }
];

export function ApiView() {
  const [status, setStatus] = useState<"checking" | "up" | "down">("checking");
  const [sample, setSample] = useState<string>("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const health = await fetch(`${API_URL}/health`);
        if (!health.ok) throw new Error();
        const point = await fetch(`${API_URL}/v1/point?lat=40.3777&lon=49.852`);
        const body = await point.json();
        if (cancelled) return;
        setStatus("up");
        setSample(JSON.stringify(body, null, 2));
      } catch {
        if (!cancelled) setStatus("down");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <>
      <div className="flex flex-wrap items-center gap-3 rounded-xl border bg-card px-5 py-4 shadow-sm">
        <span
          className={cn(
            "h-3 w-3 rounded-full",
            status === "up" && "bg-[var(--ok-500)]",
            status === "down" && "bg-[var(--err-500)]",
            status === "checking" && "bg-[var(--warn-500)]"
          )}
        />
        <div className="min-w-0 flex-1">
          <div className="text-[14px] font-semibold">
            {status === "up" ? "API işləyir" : status === "down" ? "API işləmir" : "Yoxlanılır…"}
            <span className="ml-2 font-mono text-[12px] font-normal text-muted-foreground">{API_URL}</span>
          </div>
          <div className="text-[12px] text-muted-foreground">
            {status === "down" ? (
              <>
                İşə salmaq üçün: <span className="font-mono">python scripts/serve_api.py</span>
              </>
            ) : (
              "Platforma, qiymətləndirmə modeli və ya bank sistemi indeksləri buradan alır."
            )}
          </div>
        </div>
        <a
          href={`${API_URL}/docs`}
          target="_blank"
          rel="noreferrer"
          className="rounded-md bg-[var(--brand-600)] px-3 py-1.5 text-[12px] font-semibold text-white"
        >
          İnteraktiv sənəd ↗
        </a>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <DashboardCard title="Uçlar" subtitle="Hamısı teslim cədvəlindən oxuyur, heç nə yenidən hesablanmır">
          <div className="space-y-2">
            {ENDPOINTS.map((e) => (
              <div key={e.path} className="rounded-lg border bg-background px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 font-mono text-[10.5px] font-bold text-white",
                      e.method === "GET" ? "bg-[var(--ok-500)]" : "bg-[var(--brand-600)]"
                    )}
                  >
                    {e.method}
                  </span>
                  <span className="font-mono text-[12px] font-semibold">{e.path}</span>
                </div>
                <div className="mt-1 text-[11.5px] text-muted-foreground">{e.what}</div>
                {e.method === "GET" ? (
                  <a
                    href={`${API_URL}${e.example}`}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block truncate font-mono text-[11px] text-[var(--brand-600)] hover:underline"
                  >
                    {e.example}
                  </a>
                ) : (
                  <div className="mt-1 truncate font-mono text-[11px] text-muted-foreground">{e.example}</div>
                )}
              </div>
            ))}
          </div>
        </DashboardCard>

        <DashboardCard title="Canlı cavab" subtitle="GET /v1/point?lat=40.3777&lon=49.852 — Sahil ətrafı">
          {sample ? (
            <pre className="max-h-[520px] overflow-auto rounded-lg bg-muted/50 p-3 font-mono text-[11px] leading-relaxed">
              {sample}
            </pre>
          ) : (
            <p className="text-[12px] text-muted-foreground">
              {status === "down" ? "API işə salınandan sonra burada nümunə cavab görünəcək." : "Yüklənir…"}
            </p>
          )}
        </DashboardCard>
      </div>
    </>
  );
}
