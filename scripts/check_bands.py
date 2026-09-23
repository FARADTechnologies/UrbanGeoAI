#!/usr/bin/env python
"""1–10 bantlamasının doğru çalışıp çalışmadığını sınar.

Ekibin sorusu: PCA'dan sonra 10'a bölünüyorsa, değerler birbirine çok yakın
olduğu için bütün indekslerde hücrelerin çoğu aynı bala (örneğin 9'a ya da
10'a) yığılabilir mi? Yöntemde bir hata var mı, bal gerçekten doğru bilgi
veriyor mu?

Beş soru ölçülüyor:

1. **Dağılım** — her indekste her bant kaç hücre alıyor? Taban dışındaki
   hücreler dokuz banda eşit bölünmeli (~%11); tabandaki (hiç obje yok)
   hücreler bant 1'de toplanır.
2. **Yığılma** — hücrelerin ne kadarı yedi indeksin hepsinde 9–10 ya da hepsinde
   aynı bantta?
3. **Sıralama** — büyük indeks her zaman büyük ya da eşit bant alıyor mu? Eşit
   indeks eşit bant alıyor mu? Tablodaki indeks 4 haneye yuvarlı; bu yüzden
   bant kaydedilmiş modelle yeniden hesaplanıyor ve farklar yalnız bir kesim
   noktasının yuvarlama payı içinde kalıyorsa kabul ediliyor.
4. **Anlam** — bant yükseldikçe en yakın objeye mesafe gerçekten kısalıyor mu?
5. **Ekibin yöntemi** — aynı indekse ``pd.qcut(…, duplicates="drop")``
   uygulanırsa kaç bant çıkıyor?

Kullanım:
    python scripts/check_bands.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import config, console, indices  # noqa: E402

#: İndeks → anlam kontrolü için kullanılan en yakın mesafe sütunu.
MEANING = {
    "təhsil": "distance_to_kdgr_m",
    "nəqliyyat": "distance_to_metro_m",
    "əyləncə": "distance_to_shopping_m",
    "istirahət": "distance_to_parks_m",
}


def main() -> int:
    console.use_utf8()
    parser = argparse.ArgumentParser(description=__doc__)
    settings = config.load()
    parser.add_argument(
        "--table", type=Path, default=settings.paths.output / "accessibility_indices.csv"
    )
    parser.add_argument("--json", type=Path, default=settings.paths.output / "band_check.json")
    args = parser.parse_args()

    table = pd.read_csv(args.table, encoding="utf-8")
    models = indices.load_model(args.table.with_name("index_model.json"))
    groups = [c.removesuffix("_score") for c in table.columns if c.endswith("_score")]
    n = len(table)
    result: dict = {"cells": n, "groups": groups, "per_index": {}, "cross": {}, "meaning": {}}

    print(f"{n:,} hücre · {len(groups)} indeks\n")
    print("1) DAĞILIM (%)   bant 1 = taban (hiç obje yok);  2–10 ideal ≈ eşit")
    print(
        f"   {'indeks':<14}" + "".join(f"{b:>6}" for b in range(1, 11)) + "   2–10 sapma  benzersiz"
    )
    for g in groups:
        band = table[f"{g}_score"].to_numpy()
        index = table[f"{g}_index"].to_numpy()
        share = {b: float((band == b).mean() * 100) for b in range(1, 11)}
        above = 100 - share[1]
        ideal = above / 9
        # Taban dışı dokuz bandın ideal paydan en büyük sapması (yüzde puan).
        worst = max(abs(share[b] - ideal) for b in range(2, 11))

        # 3) Sıralama. Kaydedilmiş modelle bant yeniden hesaplanır; tablodaki
        # bantla farkı olan her hücre bir kesim noktasına yuvarlama payı
        # (0.5e-4) kadar yakın olmalı.
        model = models[g]
        again = indices.apply_bands(index, model.floor, model.edges)
        cuts = np.array([model.floor, *model.edges])
        near_cut = np.min(np.abs(index[:, None] - cuts[None, :]), axis=1) <= 0.5e-4 + 1e-9
        differs = again != band
        consistent = bool((~differs | near_cut).all())
        order = np.argsort(index, kind="stable")
        monotone = bool((np.diff(again[order]) >= 0).all())
        ties = pd.DataFrame({"i": index, "b": again}).groupby("i")["b"].nunique()
        tie_consistent = bool((ties == 1).all())

        # 5) Ekibin desil yöntemi aynı indekse.
        team = pd.qcut(index, 10, labels=False, duplicates="drop") + 1

        result["per_index"][g] = {
            "share_pct": {b: round(v, 2) for b, v in share.items()},
            "floor_pct": round(share[1], 2),
            "ideal_other_pct": round(ideal, 2),
            "max_deviation_pp": round(worst, 2),
            "distinct_index_values": int(pd.Series(index).nunique()),
            "monotone": monotone,
            "stored_band_consistent": consistent,
            "stored_band_differs_near_cut": int((differs & near_cut).sum()),
            "equal_index_equal_band": tie_consistent,
            "team_method_bands": int(pd.Series(team).nunique()),
            "team_method_max": int(team.max()),
        }
        print(
            f"   {g:<14}"
            + "".join(f"{share[b]:>6.1f}" for b in range(1, 11))
            + f"   {worst:>6.2f} pp  {pd.Series(index).nunique():>8,}"
        )

    print("\n3) SIRALAMA ve 5) EKİBİN YÖNTEMİ")
    for g, r in result["per_index"].items():
        print(
            f"   {g:<14} sıralama: {r['monotone']}  eşit indeks→eşit bant: "
            f"{r['equal_index_equal_band']}  tablo tutarlı: {r['stored_band_consistent']}"
            f"   ekibin qcut'u: {r['team_method_bands']} bant (en yüksek {r['team_method_max']})"
        )

    bands = table[[f"{g}_score" for g in groups]].to_numpy()
    cross = {
        "all_ge_9_pct": round(float((bands >= 9).all(axis=1).mean() * 100), 2),
        "all_eq_10_pct": round(float((bands == 10).all(axis=1).mean() * 100), 2),
        "all_eq_1_pct": round(float((bands == 1).all(axis=1).mean() * 100), 2),
        "all_same_pct": round(float((bands.max(axis=1) == bands.min(axis=1)).mean() * 100), 2),
        "any_10_pct": round(float((bands == 10).any(axis=1).mean() * 100), 2),
        "spread_median": float(np.median(bands.max(axis=1) - bands.min(axis=1))),
        "spread_distribution_pct": {
            int(k): round(float(v) * 100, 2)
            for k, v in pd.Series(bands.max(axis=1) - bands.min(axis=1))
            .value_counts(normalize=True)
            .sort_index()
            .items()
        },
    }
    # Bağımsız olsaydı "hepsi ≥9" beklenen payı: her indeksin ≥9 payının çarpımı.
    cross["all_ge_9_if_independent_pct"] = round(
        float(np.prod([(table[f"{g}_score"] >= 9).mean() for g in groups]) * 100), 4
    )
    result["cross"] = cross
    print("\n2) YIĞILMA (yedi indeks birlikte)")
    print(
        f"   hepsi ≥ 9       : %{cross['all_ge_9_pct']}   (bağımsız olsaydı %{cross['all_ge_9_if_independent_pct']})"
    )
    print(f"   hepsi = 10      : %{cross['all_eq_10_pct']}")
    print(f"   hepsi = 1       : %{cross['all_eq_1_pct']}")
    print(f"   hepsi aynı bant : %{cross['all_same_pct']}")
    print(f"   en az biri 10   : %{cross['any_10_pct']}")
    print(f"   en yüksek − en düşük bant (medyan): {cross['spread_median']}")

    print("\n4) ANLAM — bant yükseldikçe en yakın objeye medyan mesafe (m)")
    for g, col in MEANING.items():
        if col not in table.columns:
            continue
        med = table.groupby(f"{g}_score")[col].median()
        values = [float(med.get(b, np.nan)) for b in range(1, 11)]
        valid = table[col].notna()
        rho = float(spearmanr(table.loc[valid, f"{g}_score"], table.loc[valid, col]).statistic)
        decreasing = rho < 0
        result["meaning"][g] = {
            "column": col,
            "median_m_by_band": {
                b: (None if np.isnan(v) else round(v))
                for b, v in zip(range(1, 11), values, strict=True)
            },
            "spearman_band_vs_distance": round(rho, 3),
            "decreasing": decreasing,
        }
        shown = "  ".join("—" if np.isnan(v) else f"{v:,.0f}" for v in values)
        print(f"   {g:<12} {shown}   spearman(bant, mesafe) {rho:+.3f}")

    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nJSON: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
