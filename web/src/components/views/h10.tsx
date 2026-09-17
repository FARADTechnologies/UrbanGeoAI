"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { formatCount } from "@/lib/data";
import type { Summary } from "@/types/data";

export function H10View({ summary }: { summary: Summary }) {
  const v = summary.h10;
  if (!v) {
    return (
      <DashboardCard title="H10 yoxlaması" subtitle="Hesabat tapılmadı">
        <p className="text-[12px] text-muted-foreground">
          Əvvəlcə <span className="font-mono">python scripts/verify_h10.py</span> işlədilməlidir.
        </p>
      </DashboardCard>
    );
  }

  const passed = v.checks.filter((c) => c.ok).length;

  return (
    <>
      <div
        className="flex flex-wrap items-center gap-4 rounded-xl border px-5 py-4 shadow-sm"
        style={{
          background: v.all_ok ? "var(--ok-50)" : "var(--err-50)",
          borderColor: v.all_ok ? "var(--ok-500)" : "var(--err-500)"
        }}
      >
        <div
          className="text-[30px] font-bold leading-none tabular-nums"
          style={{ color: v.all_ok ? "var(--ok-500)" : "var(--err-500)" }}
        >
          {passed}/{v.checks.length}
        </div>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-semibold">
            {v.all_ok ? "Bəli — bütün hesablama H10-da aparılır və hamısı tamdır" : "Bəzi yoxlamalar keçmədi"}
          </div>
          <div className="text-[12px] text-muted-foreground">
            Teslim cədvəli açılıb hər iddia ayrıca yoxlanıldı: {formatCount(v.rows)} sətir × {v.columns} sütun.
            Ekibin göndərdiyi orijinal kod da <b>resolution = {v.original_resolution}</b> ilə işləyir.
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <DashboardCard title="Yoxlamalar" subtitle="scripts/verify_h10.py">
          <div className="space-y-1.5">
            {v.checks.map((c) => (
              <div key={c.name} className="flex items-start gap-3 rounded-lg border bg-background px-3 py-2.5">
                <span
                  className="mt-0.5 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                  style={{ background: c.ok ? "var(--ok-500)" : "var(--err-500)" }}
                >
                  {c.ok ? "✓" : "✗"}
                </span>
                <div className="min-w-0">
                  <div className="text-[12.5px] font-medium">{c.name}</div>
                  <div className="text-[11.5px] tabular-nums text-muted-foreground">{c.detail}</div>
                </div>
              </div>
            ))}
          </div>
        </DashboardCard>

        <DashboardCard
          title="Hansı səviyyədə nə edilir"
          subtitle="Hesablama yalnız H10-da; qalanları ondan törəyir"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[440px] border-separate border-spacing-0 text-left text-[12px]">
              <thead>
                <tr>
                  {["Səviyyə", "Hüceyrə", "Rolu", "Nə var"].map((h) => (
                    <th key={h} className="border-b px-3 py-2 text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {v.levels.map((l) => (
                  <tr key={`${l.res}-${l.role}`}>
                    <td className="border-b px-3 py-2 font-semibold">H{l.res}</td>
                    <td className="border-b px-3 py-2 tabular-nums">{formatCount(l.cells)}</td>
                    <td className="border-b px-3 py-2">
                      <span
                        className="rounded-full px-2 py-0.5 text-[10.5px] font-semibold"
                        style={
                          l.res === 10
                            ? { background: "var(--brand-500)", color: "#fff" }
                            : { background: "hsl(var(--muted))", color: "hsl(var(--muted-foreground))" }
                        }
                      >
                        {l.role}
                      </span>
                    </td>
                    <td className="border-b px-3 py-2 text-muted-foreground">{l.what}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[11.5px] leading-relaxed text-muted-foreground">
            H6, H7, H8 ayrıca hesablanmır — cədvəldə hər H10 sətrinin «atası» kimi yazılıb ki, platforma
            istədiyi səviyyədə birləşdirə bilsin. Xəritədəki H7–H9 da H10 ballarının ortalamasıdır. Xəritədə
            artıq <b>H10</b> də seçilə bilir.
          </p>
        </DashboardCard>
      </div>
    </>
  );
}
