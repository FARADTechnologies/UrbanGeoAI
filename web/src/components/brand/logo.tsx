/**
 * UrbanGeoAI işarəsi.
 *
 * Platformun turuncu markası qorunur; fərq yalnız altıbucaqlı işarədir —
 * bu modul H3 şəbəkəsi üzərində işlədiyi üçün.
 */
export function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true">
      <path
        d="M16 2.6 27.6 9.3v13.4L16 29.4 4.4 22.7V9.3z"
        fill="var(--brand-500)"
      />
      <path
        d="M16 9.4 21.8 12.8v6.4L16 22.6l-5.8-3.4v-6.4z"
        fill="#fff"
        fillOpacity="0.92"
      />
    </svg>
  );
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex min-w-0 items-center gap-2">
      <Mark size={compact ? 24 : 26} />
      {!compact && (
        <span className="min-w-0 leading-tight">
          <span className="block truncate text-[13.5px] font-bold tracking-tight text-foreground">
            UrbanGeoAI
          </span>
          <span className="block truncate text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
            Əlçatanlıq indeksləri
          </span>
        </span>
      )}
    </span>
  );
}
