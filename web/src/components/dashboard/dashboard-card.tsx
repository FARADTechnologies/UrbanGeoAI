"use client";

import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

type Props = {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
};

/**
 * Standard dashboard card with head (title + subtitle + optional action)
 * and body. Wraps the existing shadcn <Card> primitive to keep all
 * cards visually consistent across the dashboard.
 */
export function DashboardCard({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-xl border bg-card text-card-foreground shadow-sm",
        className
      )}
    >
      <div className="flex items-start justify-between gap-4 border-b px-5 py-4">
        <div className="min-w-0">
          <div className="text-[13px] font-semibold tracking-tight text-foreground">
            {title}
          </div>
          {subtitle ? (
            <div className="mt-0.5 text-[11.5px] text-muted-foreground">
              {subtitle}
            </div>
          ) : null}
        </div>
        {action ? <div className="flex-shrink-0">{action}</div> : null}
      </div>
      <div className={cn("flex-1 min-h-0 p-5", bodyClassName)}>{children}</div>
    </div>
  );
}
