#!/usr/bin/env python
"""docs/pca-metodolojisi.md belgesindeki sayıları üretir ve doğrular.

Belgedeki her sayı bu betikten çıkar. Belge ile kod arasındaki tutarsızlık
burada hata olarak görünür.

Kullanım:
    python scripts/pca_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from urbangeoai import indices  # noqa: E402

# Belgedeki iki ölçümlü örnek.
SAMPLE = np.array(
    [
        [2.0, 1.0],
        [3.0, 2.5],
        [1.0, 0.5],
        [4.0, 3.5],
        [2.5, 2.0],
    ]
)


def eigen_by_hand(data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Kovaryans matrisini kurup elle özayrıştırır.

    Returns:
        (kovaryans, özdeğerler, özvektörler) — özdeğere göre azalan sırada.
    """
    centred = data - data.mean(axis=0)
    covariance = np.cov(centred, rowvar=False, ddof=1)
    values, vectors = np.linalg.eigh(covariance)
    order = np.argsort(values)[::-1]
    return covariance, values[order], vectors[:, order]


def eigen_by_svd(data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Aynı sonucu tekil değer ayrışımıyla üretir.

    Kütüphanenin izlediği yol budur: kovaryans matrisi hiç kurulmaz, bu yüzden
    sayısal olarak daha kararlıdır.
    """
    centred = data - data.mean(axis=0)
    _, singular, vt = np.linalg.svd(centred, full_matrices=False)
    eigenvalues = singular**2 / (len(data) - 1)
    return eigenvalues, vt.T


def main() -> int:
    np.set_printoptions(precision=6, suppress=True)

    print("=" * 74)
    print("1) KOVARYANS MATRİSİ")
    print("=" * 74)
    covariance, values, vectors = eigen_by_hand(SAMPLE)
    print(covariance)
    print("\nKöşegen: her ölçümün kendi varyansı.")
    print("Köşegen dışı: ikisinin birlikte değişimi. Pozitif ise birlikte artıyorlar.")

    print("\n" + "=" * 74)
    print("2) ÖZDEĞER VE ÖZVEKTÖR")
    print("=" * 74)
    ratio = values / values.sum()
    for i, (value, ratio_i) in enumerate(zip(values, ratio, strict=True), start=1):
        vector = vectors[:, i - 1]
        print(
            f"  PC{i}  λ={value:.6f}  v=({vector[0]:+.6f}, {vector[1]:+.6f})  "
            f"açıklanan varyans={ratio_i:.2%}"
        )

    check = np.allclose(covariance @ vectors[:, 0], values[0] * vectors[:, 0])
    print(f"\n  C · v₁ = λ₁ · v₁  doğrulaması: {check}")
    assert check, "özayrışım tanımı sağlanmıyor"

    print("\n" + "=" * 74)
    print("3) ÖZAYRIŞIM İLE TEKİL DEĞER AYRIŞIMI AYNI SONUCU VERİR")
    print("=" * 74)
    svd_values, svd_vectors = eigen_by_svd(SAMPLE)
    print(f"  özayrışım özdeğerleri : {values}")
    print(f"  SVD özdeğerleri       : {svd_values}")
    assert np.allclose(values, svd_values), "iki yöntem farklı özdeğer veriyor"

    # Özvektörler işaret farkı taşıyabilir; yön aynı olmalı.
    aligned = np.allclose(np.abs(vectors[:, 0]), np.abs(svd_vectors[:, 0]))
    print(f"  birinci özvektör yönü aynı: {aligned}")
    assert aligned, "iki yöntem farklı yön veriyor"
    print("\n  İşaret farkı olabilir; matematiksel olarak ikisi de geçerlidir.")
    print("  Projede bu belirsizlik açıkça sabitleniyor (bkz. 4. bölüm).")

    print("\n" + "=" * 74)
    print("4) İŞARET BELİRSİZLİĞİ VE SABİTLEME")
    print("=" * 74)
    import pandas as pd

    rising = pd.DataFrame({"a_score": SAMPLE[:, 0], "b_score": SAMPLE[:, 1]})
    falling = pd.DataFrame({"a_score": -SAMPLE[:, 0], "b_score": -SAMPLE[:, 1]})

    for label, frame in (("artan", rising), ("azalan", falling)):
        model = indices.fit_group(frame, ["a", "b"])
        total = sum(model.components)
        print(
            f"  {label:<8} yükler=({model.components[0]:+.4f}, "
            f"{model.components[1]:+.4f})  toplam={total:+.4f}"
        )
        assert total > 0, "işaret sabitlemesi çalışmıyor"

    print("\n  İki durumda da yükler pozitif: yüksek indeks daima")
    print("  'daha erişilebilir' anlamına geliyor.")

    print("\n" + "=" * 74)
    print("5) STANDARTLAŞTIRMA NEDEN ZORUNLU")
    print("=" * 74)
    rng = np.random.default_rng(0)
    base = rng.normal(0, 1, 500)
    # Bir ölçüm çok daha büyük ölçekte; projede kafe ile metro arasındaki fark.
    wide = pd.DataFrame({"big_score": base * 100, "small_score": base + rng.normal(0, 0.1, 500)})

    unscaled_cov = np.cov(wide.to_numpy(), rowvar=False)
    _, unscaled_vectors = np.linalg.eigh(unscaled_cov)
    dominant = unscaled_vectors[:, -1]
    print(f"  ölçeklenmemiş birinci yön: ({dominant[0]:+.4f}, {dominant[1]:+.4f})")
    print("  büyük ölçekli ölçüm yönü tek başına belirliyor")

    model = indices.fit_group(wide, ["big", "small"])
    print(f"  standartlaştırılmış yükler: ({model.components[0]:+.4f}, {model.components[1]:+.4f})")
    print("  iki ölçüm de eşit ağırlıkla katkı veriyor")

    print("\n" + "=" * 74)
    print("BÜTÜN DOĞRULAMALAR GEÇTİ")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
