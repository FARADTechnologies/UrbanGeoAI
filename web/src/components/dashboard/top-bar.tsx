"use client";

import { Moon, Sun } from "lucide-react";

import { useTheme } from "@/components/theme-provider";

type Props = {
  title: string;
  subtitle: string;
  /** Sağ tərəfdə görünən əlavə nəzarətlər (məsələn xəritə seçiciləri). */
  children?: React.ReactNode;
};

export function TopBar({ title, subtitle, children }: Props) {
  const { theme, toggle } = useTheme();

  return (
    <header className="flex flex-shrink-0 items-center gap-4 border-b bg-card/60 px-5 py-3 backdrop-blur">
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-[15px] font-semibold tracking-tight">{title}</h1>
        <p className="truncate text-[11.5px] text-muted-foreground">{subtitle}</p>
      </div>

      {children}

      <button
        type="button"
        onClick={toggle}
        title={theme === "dark" ? "İşıqlı rejim" : "Qaranlıq rejim"}
        aria-label={theme === "dark" ? "İşıqlı rejim" : "Qaranlıq rejim"}
        className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md border text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
      >
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </button>
    </header>
  );
}
