"use client";

import {
  Activity,
  BadgeCheck,
  Database,
  Plug,
  GitCompareArrows,
  LayoutDashboard,
  Lightbulb,
  Map as MapIcon,
  PanelLeftClose,
  PanelLeftOpen,
  ShieldCheck,
  TrainFront
} from "lucide-react";

import { Wordmark } from "@/components/brand/logo";
import { cn } from "@/lib/utils";

export type View =
  | "overview"
  | "map"
  | "enrichment"
  | "h10"
  | "api"
  | "indices"
  | "metro"
  | "validation"
  | "change"
  | "proposals";

type NavItem = {
  id: View;
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  pill?: string;
};

type Props = {
  active: View;
  onChange: (view: View) => void;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  /** Rozet sayıları — yüklenene kadar gizli. */
  badges?: Partial<Record<View, string>>;
};

const ITEMS: Omit<NavItem, "pill">[] = [
  { id: "overview", icon: LayoutDashboard, label: "İcmal" },
  { id: "map", icon: MapIcon, label: "Xəritə" },
  { id: "enrichment", icon: Database, label: "OSM zənginləşdirmə" },
  { id: "h10", icon: BadgeCheck, label: "H10 yoxlaması" },
  { id: "indices", icon: Activity, label: "İndekslər" },
  { id: "metro", icon: TrainFront, label: "Metro" },
  { id: "validation", icon: ShieldCheck, label: "Veri denetimi" },
  { id: "change", icon: GitCompareArrows, label: "Dəyişim" },
  { id: "proposals", icon: Lightbulb, label: "Təkliflər" },
  { id: "api", icon: Plug, label: "API" }
];

export function NavSidebar({ active, onChange, collapsed, onToggleCollapsed, badges }: Props) {
  const toggleLabel = collapsed ? "Yan paneli aç" : "Yan paneli bağla";

  return (
    <nav className={cn("flex flex-col gap-2 py-4", collapsed ? "px-2" : "px-3")}>
      <div
        className={cn(
          "sticky top-0 z-10 -mt-4 mb-1 flex items-center border-b bg-card py-3",
          collapsed ? "-mx-2 justify-center px-2" : "-mx-3 gap-2 px-4"
        )}
      >
        {collapsed ? <Wordmark compact /> : <div className="min-w-0 flex-1"><Wordmark /></div>}
        <button
          type="button"
          onClick={onToggleCollapsed}
          title={`${toggleLabel} (Ctrl+B)`}
          aria-label={toggleLabel}
          aria-expanded={!collapsed}
          className={cn(
            "flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground",
            collapsed && "hidden"
          )}
        >
          <PanelLeftClose className="h-4 w-4" />
        </button>
      </div>

      {collapsed ? (
        <button
          type="button"
          onClick={onToggleCollapsed}
          title={`${toggleLabel} (Ctrl+B)`}
          aria-label={toggleLabel}
          className="mx-auto flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
        >
          <PanelLeftOpen className="h-4 w-4" />
        </button>
      ) : null}

      <div className="flex flex-col gap-0.5">
        {ITEMS.map((item) => (
          <NavRow
            key={item.id}
            item={{ ...item, pill: badges?.[item.id] }}
            active={active === item.id}
            collapsed={collapsed}
            onClick={() => onChange(item.id)}
          />
        ))}
      </div>

      {!collapsed ? (
        <div className="mt-auto px-2 pt-6 text-[10.5px] leading-relaxed text-muted-foreground">
          Panel boru hattının çıxışını oxuyur. Rəqəmlər əl ilə yazılmır —
          <span className="font-medium text-foreground"> build_web_data.py</span> hər dəfə
          yenidən hesablayır.
        </div>
      ) : null}
    </nav>
  );
}

function NavRow({
  item,
  active,
  collapsed,
  onClick
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
  onClick: () => void;
}) {
  const Icon = item.icon;
  return (
    <button
      type="button"
      onClick={onClick}
      title={collapsed ? item.label : undefined}
      aria-label={collapsed ? item.label : undefined}
      className={cn(
        "flex h-9 items-center rounded-lg text-[12.5px] font-medium transition-colors",
        collapsed ? "justify-center px-0" : "gap-2.5 px-2.5",
        active
          ? "bg-[var(--brand-600)] text-white shadow-sm"
          : "text-muted-foreground hover:bg-muted/60 hover:text-foreground"
      )}
    >
      <Icon className="h-3.5 w-3.5 flex-shrink-0" />
      {!collapsed && <span className="flex-1 truncate text-left">{item.label}</span>}
      {!collapsed && item.pill ? (
        <span
          className={cn(
            "rounded-full px-1.5 py-0.5 text-[9.5px] font-bold tracking-wider",
            active ? "bg-white/20 text-white" : "bg-muted text-muted-foreground"
          )}
        >
          {item.pill}
        </span>
      ) : null}
    </button>
  );
}
