#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi
from logic.maliyet import mamul_tum_satirlar

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

bom = bom_listesi(conn)

# GMP-200-230602 BOM'da artik gorunu$uyor mu?
print("=== GMP-200-230602 BOM'daki bilesenleri ===")
p = bom.get("GMP-200-230602")
if p:
    print(f"  {len(p['bilesenleri'])} bilesen:")
    for b in p["bilesenleri"]:
        print(f"  {b['kod']:<30} {b['ad'][:40]}")
else:
    print("  BOM'da yok")

# GMP-101-230014 tam patlama
print("\n=== GMP-101-230014 tam BOM patlamasi ===")
satirlar, toplam = mamul_tum_satirlar(
    conn, "GMP-101-230014", "WA", "01.01.2024", "31.12.2024", bom
)
print(f"Toplam: {toplam:,.2f} TL  |  {len(satirlar)} satir\n")

print(f"{'Tip':<12} {'Sev':<4} {'Kod':<28} {'Ad':<35} {'Miktar':>7} {'BirimMal':>12} {'SatirTop':>12}")
print("-" * 115)
for s in satirlar:
    sev = s.get("seviye", 1)
    indent = "  " * (sev - 1)
    print(f"{s['tip']:<12} {sev:<4} {s['kod']:<28} {indent+s['ad'][:33-len(indent)*2]:<35} "
          f"{s['bom_miktar']:>7.2f} {s['birim_mal']:>12.4f} {s['satir_top']:>12.2f}")
