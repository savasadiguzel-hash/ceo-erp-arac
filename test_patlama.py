#!/usr/bin/env python3
"""Tam BOM patlamasi testi - GMP-101-230022 en alt bilesenlere kadar"""

import os
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi
from logic.maliyet import mamul_tum_satirlar
from logic.excel import maliyet_excel_kaydet

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

bom = bom_listesi(conn)
mamul = "GMP-101-230022"  # BORESIGHTER SP 7,62 OTOKAR - 5 bileseni var

print(f"Mamul: {mamul}")
print(f"Aciklama: {bom[mamul]['ad']}\n")

cache = {}
satirlar, toplam = mamul_tum_satirlar(
    conn, mamul, 'WA', '01.01.2024', '31.12.2024', bom, _cache=cache
)

print(f"Toplam Malzeme Maliyeti: {toplam:,.2f} TL")
print(f"Toplam Satir Sayisi: {len(satirlar)}\n")

print(f"{'Tip':<12} {'Sev':<5} {'Kod':<25} {'Ad':<35} {'Miktar':<8} {'BirimMal':>12} {'SatirTop':>12}")
print("-" * 115)
for s in satirlar:
    sev = s.get('seviye', 1)
    girinti = "  " * (sev - 1)
    tip = s['tip']
    print(f"{tip:<12} {sev:<5} {s['kod']:<25} {girinti + s['ad'][:32]:<35} {s['bom_miktar']:<8.3f} {s['birim_mal']:>12.4f} {s['satir_top']:>12.2f}")

# Excel de olustur
dosya = "C:/yeni-erp/test_patlama.xlsx"
maliyet_excel_kaydet(
    dosya, conn, [(mamul, 500.0)],
    metod='WA', bas='01.01.2024', bit='31.12.2024',
    bas_g='01.01.2024', bit_g='31.12.2024'
)
print(f"\nExcel olusturuldu: {dosya} ({os.path.getsize(dosya):,} bytes)")
