import type { Metadata } from "next";

import { ThemeProvider } from "@/components/theme-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "UrbanGeoAI — Əlçatanlıq indeksləri",
  description:
    "Bakı və Abşeron üçün H3 şəbəkəsi üzərində əlçatanlıq indeksləri: təhsil, nəqliyyat, turizm, yemək, istirahət, əyləncə və təhlükəsizlik.",
  // Panel iş ortağının verisini göstərir; axtarış motorlarına düşməsin.
  robots: { index: false, follow: false }
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="az" data-theme="light" suppressHydrationWarning>
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
