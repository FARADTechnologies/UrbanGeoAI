"use client";

import {
  BookOpen,
  Check,
  Clock,
  Copy,
  ExternalLink,
  Globe,
  Instagram,
  MapPin,
  Phone,
  Star,
  Table2,
  Utensils,
  X
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  categoryColor,
  categoryLabel,
  googleMapsUrl,
  imageUrl,
  instagramUrl,
  loadPoiInfo,
  osmUrl,
  safeUrl,
  wikipediaUrl
} from "@/lib/data";
import type { PoiDetail, PoiSelection } from "@/types/data";

export type CardTarget = PoiSelection & { lat: number; lon: number; x: number; y: number };

const WIDTH = 300;

function Row({ icon: Icon, children }: { icon: React.ComponentType<{ className?: string }>; children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 py-1">
      <Icon className="mt-[2px] h-3.5 w-3.5 flex-shrink-0 opacity-60" />
      <div className="min-w-0 flex-1 break-words">{children}</div>
    </div>
  );
}

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-[#fdba74] underline-offset-2 hover:underline"
    >
      {children}
    </a>
  );
}

/**
 * Xəritədə obyektə klikləyəndə açılan kart. Siçan kartın üzərinə keçə bilsin
 * deyə sabit qalır; X, Esc və ya xəritədə boş yerə klik bağlayır.
 */
export function PoiCard({
  target,
  bounds,
  onClose,
  onShowInTable
}: {
  target: CardTarget;
  bounds: { width: number; height: number };
  onClose: () => void;
  onShowInTable?: (selection: PoiSelection) => void;
}) {
  const [detail, setDetail] = useState<PoiDetail | null | undefined>(undefined);
  const [copied, setCopied] = useState(false);
  const [imageOk, setImageOk] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setDetail(undefined);
    setImageOk(true);
    void loadPoiInfo().then((info) => {
      if (!cancelled) setDetail(info?.[target.key]?.[target.category]?.[target.index] ?? null);
    });
    return () => {
      cancelled = true;
    };
  }, [target.key, target.category, target.index]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const coords = `${target.lat.toFixed(6)}, ${target.lon.toFixed(6)}`;
  const copy = () => {
    void navigator.clipboard?.writeText(coords).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    });
  };

  // Kart kliklənən nöqtənin yanında; kənara çıxarsa o biri tərəfə keçir.
  const estimatedHeight = 380;
  let x = target.x + 16;
  let y = target.y - 40;
  if (x + WIDTH > bounds.width - 8) x = target.x - WIDTH - 16;
  if (y + estimatedHeight > bounds.height - 8) y = bounds.height - estimatedHeight - 8;
  x = Math.max(8, x);
  y = Math.max(8, y);

  const d = detail ?? {};
  const image = detail ? imageUrl(detail) : null;
  const web = safeUrl(d.web);
  const osm = osmUrl(d.id);
  const wiki = wikipediaUrl(d.wikipedia);
  const insta = instagramUrl(d.instagram);
  const color = categoryColor(target.category);
  const source =
    target.key === "osm"
      ? "OpenStreetMap-dən əlavə"
      : target.category === "metro"
        ? "OpenStreetMap · metro"
        : target.key === "2025"
          ? "İş ortağı · 2025"
          : "İş ortağının verisi";

  return (
    <div
      role="dialog"
      aria-label="Obyekt məlumatı"
      className="pointer-events-auto absolute z-30 overflow-hidden rounded-xl border border-white/10 bg-[#10161f]/97 text-[12px] text-[#f5f7fb] shadow-2xl backdrop-blur"
      style={{ left: x, top: y, width: WIDTH }}
      onMouseDown={(e) => e.stopPropagation()}
      onWheel={(e) => e.stopPropagation()}
    >
      <div className="h-1 w-full" style={{ background: color }} />

      {image && imageOk ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={image}
          alt=""
          className="h-36 w-full object-cover"
          loading="lazy"
          onError={() => setImageOk(false)}
        />
      ) : null}

      <div className="p-3">
        <div className="flex items-start gap-2">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-1.5 text-[10.5px] uppercase tracking-wider opacity-70">
              <span className="inline-block h-2 w-2 rounded-full" style={{ background: color }} />
              {categoryLabel(target.category)}
            </div>
            <div className="mt-0.5 text-[14px] font-semibold leading-snug">
              {detail === undefined ? "…" : d.n || <span className="opacity-60">adsız</span>}
            </div>
            {d.o ? <div className="text-[10.5px] opacity-55">orijinal: {d.o}</div> : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Bağla"
            className="-mr-1 -mt-1 rounded-md p-1 opacity-60 hover:bg-white/10 hover:opacity-100"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-2 flex flex-wrap gap-1">
          <span className="rounded-full bg-white/10 px-2 py-0.5 text-[10px]">{source}</span>
          {d.m ? (
            <span className="rounded-full bg-[#16a34a]/25 px-2 py-0.5 text-[10px] text-[#86efac]">
              OSM-də eyni adla var
            </span>
          ) : null}
        </div>

        <div className="mt-2 border-t border-white/10 pt-1.5">
          <Row icon={MapPin}>
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-[11px]">{coords}</span>
              <button
                type="button"
                onClick={copy}
                className="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10.5px] opacity-70 hover:bg-white/10 hover:opacity-100"
              >
                {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
                {copied ? "kopyalandı" : "kopyala"}
              </button>
            </div>
            {d.addr ? <div className="opacity-75">{d.addr}</div> : null}
          </Row>
          {d.hours ? <Row icon={Clock}>{d.hours}</Row> : null}
          {d.phone ? (
            <Row icon={Phone}>
              <a href={`tel:${d.phone.replace(/[^\d+]/g, "")}`} className="hover:underline">
                {d.phone}
              </a>
            </Row>
          ) : null}
          {web ? (
            <Row icon={Globe}>
              <Ext href={web}>{web.replace(/^https?:\/\//, "").replace(/\/$/, "")}</Ext>
            </Row>
          ) : null}
          {insta ? (
            <Row icon={Instagram}>
              <Ext href={insta}>Instagram</Ext>
            </Row>
          ) : null}
          {d.cuisine ? <Row icon={Utensils}>{d.cuisine.replaceAll(";", ", ")}</Row> : null}
          {d.stars ? <Row icon={Star}>{d.stars} ulduz</Row> : null}
          {wiki ? (
            <Row icon={BookOpen}>
              <Ext href={wiki}>Vikipediya</Ext>
            </Row>
          ) : null}
          {detail !== undefined && !web && !d.phone && !d.hours && !d.addr ? (
            <div className="py-1 text-[10.5px] opacity-50">Əlavə məlumat yoxdur (mənbədə yalnız ad və koordinat var).</div>
          ) : null}
        </div>

        <div className="mt-2.5 grid grid-cols-2 gap-1.5">
          <a
            href={googleMapsUrl(target.lat, target.lon)}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center justify-center gap-1.5 rounded-lg bg-[#ea580c] px-2 py-1.5 text-[11.5px] font-semibold text-white hover:bg-[#c2410c]"
          >
            <ExternalLink className="h-3.5 w-3.5" /> Google Maps
          </a>
          {onShowInTable ? (
            <button
              type="button"
              onClick={() => onShowInTable({ key: target.key, category: target.category, index: target.index })}
              className="flex items-center justify-center gap-1.5 rounded-lg bg-white/10 px-2 py-1.5 text-[11.5px] font-semibold hover:bg-white/20"
            >
              <Table2 className="h-3.5 w-3.5" /> Cədvəldə göstər
            </button>
          ) : null}
        </div>
        {osm ? (
          <div className="mt-1.5 text-center text-[10.5px] opacity-60">
            <Ext href={osm}>OpenStreetMap-də bax</Ext>
          </div>
        ) : null}
      </div>
    </div>
  );
}
