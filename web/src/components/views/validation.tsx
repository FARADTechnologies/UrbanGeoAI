"use client";

import { DashboardCard } from "@/components/dashboard/dashboard-card";
import { formatCount } from "@/lib/data";
import type { FileReport, Summary } from "@/types/data";

const SEVERITY: Record<string, { label: string; tone: string }> = {
  error: { label: "Xəta", tone: "var(--err-500)" },
  warning: { label: "Xəbərdarlıq", tone: "var(--warn-500)" },
  info: { label: "Məlumat", tone: "var(--ink-400)" }
};

function worst(report: FileReport) {
  if (report.unreadable) return "error";
  if (report.findings.some((f) => f.severity === "error")) return "error";
  if (report.findings.some((f) => f.severity === "warning")) return "warning";
  return report.findings.length > 0 ? "info" : "ok";
}

export function ValidationView({ summary }: { summary: Summary }) {
  const reports = [...summary.validation].sort((a, b) => {
    const order = { error: 0, warning: 1, info: 2, ok: 3 } as Record<string, number>;
    return order[worst(a)] - order[worst(b)];
  });

  const counts = reports.reduce(
    (acc, r) => {
      const key = worst(r);
      acc[key] = (acc[key] ?? 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  return (
    <>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          { key: "error", label: "Xətalı fayl" },
          { key: "warning", label: "Xəbərdarlıqlı" },
          { key: "info", label: "Yalnız məlumat" },
          { key: "ok", label: "Təmiz" }
        ].map((row) => (
          <div key={row.key} className="rounded-xl border bg-card px-4 py-3 shadow-sm">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">
              {row.label}
            </div>
            <div
              className="mt-1 text-[21px] font-bold leading-none tabular-nums"
              style={{ color: SEVERITY[row.key]?.tone ?? "var(--ok-500)" }}
            >
              {counts[row.key] ?? 0}
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        {reports.map((report) => (
          <DashboardCard
            key={report.file}
            title={<span className="font-mono text-[12px]">{report.file}</span>}
            subtitle={`${formatCount(report.rows)} sətir · ${report.columns.length} sütun`}
          >
            {report.unreadable ? (
              <p className="text-[12px] text-[var(--err-500)]">{report.unreadable}</p>
            ) : report.findings.length === 0 ? (
              <p className="text-[12px] text-[var(--ok-500)]">Bulgu yoxdur.</p>
            ) : (
              <div className="space-y-1.5">
                {report.findings.map((finding, i) => {
                  const meta = SEVERITY[finding.severity] ?? SEVERITY.info;
                  return (
                    <div
                      key={`${finding.check}-${i}`}
                      className="flex items-start gap-2.5 rounded-lg border bg-background px-3 py-2"
                    >
                      <span
                        className="mt-[3px] h-2 w-2 flex-shrink-0 rounded-full"
                        style={{ background: meta.tone }}
                        title={meta.label}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="text-[12px]">{finding.message}</div>
                        <div className="mt-0.5 font-mono text-[10.5px] text-muted-foreground">
                          {finding.check}
                        </div>
                      </div>
                      <span className="flex-shrink-0 text-[12px] font-semibold tabular-nums">
                        {formatCount(finding.count)}
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
          </DashboardCard>
        ))}
      </div>
    </>
  );
}
