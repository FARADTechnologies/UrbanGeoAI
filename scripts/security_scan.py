#!/usr/bin/env python
"""Push öncesi güvenlik ve gizlilik taraması.

Depoya girmek üzere olan içeriği tarar. Yalnızca dosya adlarına değil,
dosyaların içeriğine bakar. Bulgu varsa sıfırdan farklı kod döndürür.

Kullanım:
    python scripts/security_scan.py            # staged içerik
    python scripts/security_scan.py --tracked  # takip edilen bütün dosyalar
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_KB = 2048

# (ad, desen, açıklama). Desenler kaynak koda değil, sızıntıya odaklıdır.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Gizli anahtar",
        re.compile(r"-----BEGIN (RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----"),
        "Özel anahtar bloğu",
    ),
    (
        "AWS anahtarı",
        re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
        "AWS erişim anahtarı kimliği",
    ),
    (
        "GitHub token",
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}\b"),
        "GitHub kişisel erişim belirteci",
    ),
    (
        "Slack token",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
        "Slack belirteci",
    ),
    (
        "Genel API anahtarı",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)"
            r"\s*[:=]\s*[\"'][A-Za-z0-9_\-./+]{16,}[\"']"
        ),
        "Koda gömülü anahtar",
    ),
    (
        "Bağlantı dizesi",
        re.compile(r"(?i)\b(postgres(ql)?|mysql|mongodb(\+srv)?|redis)://[^\s\"'<>]*:[^\s\"'<>@]+@"),
        "Parola içeren veritabanı adresi",
    ),
    (
        "Parola ataması",
        re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*[\"'][^\"'{}$\s]{6,}[\"']"),
        "Koda gömülü parola",
    ),
    (
        "Yerel yol",
        re.compile(r"[A-Za-z]:\\Users\\|/Users/[a-z][A-Za-z0-9_.-]*/|/home/[a-z][A-Za-z0-9_.-]*/"),
        "Mutlak yerel makine yolu",
    ),
    (
        "E-posta adresi",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "Kişisel e-posta adresi",
    ),
]

# Yanlış pozitifleri elemek için. Bu ifadeler bulguyu geçersiz kılar.
ALLOW = re.compile(
    r"(?i)"
    r"noreply@|example\.com|example\.org|localhost|"
    r"openstreetmap\.org|gadm\.org|ucdavis\.edu|"
    r"\$\{|<yerel yol>|your[_-]?key|xxx+|placeholder|"
    r"api\.key|apikey_here"
)

TEXT_SUFFIXES = {
    ".py", ".ipynb", ".md", ".yml", ".yaml", ".toml", ".cfg", ".ini",
    ".txt", ".json", ".csv", ".sh", ".html", ".js", ".ts", ".sql", "",
}


def staged_files() -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        capture_output=True, text=True, check=True,
    )
    return [f for f in out.stdout.splitlines() if f.strip()]


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [f for f in out.stdout.splitlines() if f.strip()]


def scan_file(path: Path) -> list[tuple[int, str, str, str]]:
    """Tek dosyayı tarar. (satır, kural, açıklama, kesit) listesi döndürür."""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    findings = []
    for lineno, line in enumerate(content.splitlines(), start=1):
        if ALLOW.search(line):
            continue
        for name, pattern, description in PATTERNS:
            match = pattern.search(line)
            if match:
                snippet = line.strip()
                if len(snippet) > 100:
                    snippet = snippet[:100] + "…"
                findings.append((lineno, name, description, snippet))
                break
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracked", action="store_true",
                        help="Staged yerine takip edilen bütün dosyaları tara")
    args = parser.parse_args()

    files = tracked_files() if args.tracked else staged_files()
    if not files:
        print("Taranacak dosya yok.")
        return 0

    scope = "takip edilen" if args.tracked else "staged"
    print(f"{len(files)} {scope} dosya taranıyor…\n")

    problems = 0

    for name in files:
        path = Path(name)
        if not path.exists():
            continue

        size_kb = path.stat().st_size // 1024
        if size_kb > MAX_FILE_KB:
            print(f"  BÜYÜK DOSYA  {name}  ({size_kb} KB > {MAX_FILE_KB} KB)")
            problems += 1

        for lineno, rule, description, snippet in scan_file(path):
            print(f"  {rule.upper():<18} {name}:{lineno}")
            print(f"  {'':<18} {description}")
            print(f"  {'':<18} {snippet}\n")
            problems += 1

    print()
    if problems:
        print(f"TARAMA BAŞARISIZ: {problems} bulgu. Push edilmemeli.")
        return 1

    print("TARAMA TEMİZ: gizli bilgi, kişisel veri veya yerel yol bulunamadı.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
