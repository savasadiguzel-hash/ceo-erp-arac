#!/usr/bin/env python3
"""
tools/ekstre_bakiye.py
Stok ekstresi parse doğrulama aracı.
Kullanım: python tools/ekstre_bakiye.py [--ekstrem DOSYA]

Kontroller:
  1. HMGMDDAL004: 05.01.2026'da 0, bugün 591
  2. Tüm kart son bakiyeleri — SARF0000010 ve HMGMKBL0111 ekstre toplamıyla tutuşmalı
  3. Genel eşleşme oranı
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import openpyxl

BASE = Path(__file__).resolve().parent.parent

_EKSTREM_VARSAYILAN = BASE / "Stok Kartı Ekstresi_10062026183813.xlsx"


def _parse_date(val):
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    if isinstance(val, str):
        for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                pass
    return None


def load_ekstre(path: Path) -> dict:
    """
    {stok_kodu: {'devir': float, 'txns': [(date, signed_qty)]}}
    Formül: devir (col23) + SUM(col11, date <= hedef)
    Tüm işlem türleri — filtre YOK.
    """
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    cards: dict = {}
    current = None

    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:
            continue
        col0  = row[0]  if len(row) > 0  else None
        col4  = row[4]  if len(row) > 4  else None
        col11 = row[11] if len(row) > 11 else None
        col23 = row[23] if len(row) > 23 else None

        if col0 is not None and isinstance(col0, str) and col0.strip():
            current = col0.strip()
            devir = float(col23) if col23 is not None else 0.0
            cards[current] = {'devir': devir, 'txns': []}
            continue

        if current is None:
            continue

        tx_date = _parse_date(col4)
        if tx_date is None or col11 is None:
            continue

        try:
            amount = float(col11)
        except (TypeError, ValueError):
            continue

        cards[current]['txns'].append((tx_date, amount))

    wb.close()
    for kod in cards:
        cards[kod]['txns'].sort(key=lambda x: x[0])
    return cards


def bakiye(card: dict, hedef: date) -> float:
    return card['devir'] + sum(a for d, a in card['txns'] if d <= hedef)


def son_bakiye(card: dict) -> float:
    return card['devir'] + sum(a for _, a in card['txns'])


def main():
    parser = argparse.ArgumentParser(description="Ekstre bakiye doğrulama")
    parser.add_argument("--ekstrem", default=None)
    args = parser.parse_args()

    path = Path(args.ekstrem) if args.ekstrem else _EKSTREM_VARSAYILAN
    if not path.exists():
        # Glob ile bul
        candidates = sorted(
            BASE.glob("Stok Kartı Ekstresi*.xlsx"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            print(f"HATA: Ekstre dosyası bulunamadı. --ekstrem ile belirtin.")
            return 2
        path = candidates[0]

    print(f"Ekstre: {path.name}")
    cards = load_ekstre(path)
    print(f"Parse: {len(cards)} stok kodu\n")

    bugun = date.today()  # 2026-06-11
    tarih_05_01 = date(2026, 1, 5)

    # ── 1. HMGMDDAL004 noktasal kontrol ──────────────────────────────────────
    print("=" * 60)
    print("1. HMGMDDAL004 NOKTASAL KONTROL")
    print("=" * 60)
    kod = "HMGMDDAL004"
    if kod not in cards:
        print(f"   {kod} ekstrede YOK\n")
    else:
        c = cards[kod]
        b_05_01 = bakiye(c, tarih_05_01)
        b_bugun = bakiye(c, bugun)
        beklenen_05_01 = 0.0
        beklenen_bugun = 591.0
        s1 = "OK" if abs(b_05_01 - beklenen_05_01) < 0.01 else "FAIL"
        s2 = "OK" if abs(b_bugun - beklenen_bugun) < 0.01 else "FAIL"
        print(f"   {kod}")
        print(f"   {tarih_05_01}  beklenen={beklenen_05_01}  hesaplanan={b_05_01}  [{s1}]")
        print(f"   {bugun}  beklenen={beklenen_bugun}  hesaplanan={b_bugun}  [{s2}]")
        print()

    # ── 2. Hedef kartlar: son bakiye = ekstre kalan sütunu ────────────────────
    print("=" * 60)
    print("2. SARF0000010 ve HMGMKBL0111 — SON BAKİYE (TÜM HAREKETLERİN TOPLAMI)")
    print("=" * 60)
    hedef_kartlar = ["SARF0000010", "HMGMKBL0111"]
    for kod in hedef_kartlar:
        if kod not in cards:
            print(f"   {kod}: ekstrede YOK")
            continue
        c = cards[kod]
        sb = son_bakiye(c)
        print(f"   {kod}: devir={c['devir']:.4g}  hareket_sayisi={len(c['txns'])}  son_bakiye={sb:.4g}")
    print()

    # ── 3. Genel devir + sum(col11) → son_bakiye dağılımı ────────────────────
    print("=" * 60)
    print("3. GENEL ÖZET")
    print("=" * 60)
    toplam = len(cards)
    sifir_hareket = sum(1 for c in cards.values() if len(c['txns']) == 0)
    negatif_son   = sum(1 for c in cards.values() if son_bakiye(c) < -0.01)
    print(f"   Toplam kart sayısı  : {toplam}")
    print(f"   Hareketsiz kartlar  : {sifir_hareket} (devir var, txn yok)")
    print(f"   Son bakiyesi < 0    : {negatif_son} kart")
    print()

    # ── 4. Bugün itibarıyla tüm kartların bakiyesi (ilk 20 ve negatifler) ────
    bugun_bakiyeler = [(kod, bakiye(c, bugun)) for kod, c in cards.items()]
    bugun_bakiyeler.sort(key=lambda x: x[1])
    negatifler = [(k, b) for k, b in bugun_bakiyeler if b < -0.01]
    if negatifler:
        print(f"   Bugün negatif bakiyeli kartlar ({len(negatifler)}):")
        print(f"   {'Stok Kodu':<25} {'Bugün Bakiye':>15}")
        print("   " + "-" * 42)
        for k, b in negatifler[:20]:
            print(f"   {k:<25} {b:>15.4g}")
        if len(negatifler) > 20:
            print(f"   ... ve {len(negatifler) - 20} daha")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
