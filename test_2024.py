#!/usr/bin/env python3
"""Exe ile ayni akisi simule et - 2024 tarihleri, WA yontemi"""

import os
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi
from logic.excel import maliyet_excel_kaydet

BAS = "01.01.2024"
BIT = "31.12.2024"
METOD = "WA"
DOSYA = "C:/yeni-erp/maliyet_2024_test.xlsx"

print(f"Tarih: {BAS} - {BIT}")
print(f"Yontem: {METOD}\n")

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])
print("[OK] Veritabani baglantisi kuruldu")

bom = bom_listesi(conn)
print(f"[OK] {len(bom)} mamul BOM yuklendi")

# Bilesenleri olan tum mamulleri sec (exe'deki gibi hepsini sec)
secili = [(k, 0.0) for k, v in bom.items() if v['bilesenleri']]
print(f"[OK] {len(secili)} mamul hesaplanacak\n")

print("-" * 70)

sonuclar = []
def ilerleme(msg):
    print(f"  {msg}")

try:
    maliyet_excel_kaydet(
        DOSYA, conn, secili,
        metod=METOD,
        bas=BAS, bit=BIT,
        bas_g=BAS, bit_g=BIT,
        ilerleme_cb=ilerleme
    )

    size = os.path.getsize(DOSYA)
    print(f"\n[OK] Excel olusturuldu: {DOSYA}")
    print(f"     Boyut: {size:,} bytes ({size/1024:.1f} KB)")

except Exception as e:
    print(f"\n[HATA] {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Sonuclari dogrudan hesapla ve goster
print("\n" + "=" * 70)
print("MALIYET OZETI (0 TL haric)")
print("=" * 70)

from logic.maliyet import mamul_maliyet_hesapla
cache = {}
sifir_sayisi = 0
dolu_sayisi = 0

for mamul_kod, _ in secili:
    satirlar, toplam = mamul_maliyet_hesapla(
        conn, mamul_kod, METOD, BAS, BIT, _cache=cache
    )
    if toplam > 0:
        dolu_sayisi += 1
        ad = bom[mamul_kod]['ad']
        print(f"  {mamul_kod:<25} {ad[:30]:<30} {toplam:>12,.2f} TL")
    else:
        sifir_sayisi += 1

print("-" * 70)
print(f"  Maliyet hesaplanan: {dolu_sayisi} mamul")
print(f"  0 TL cikan:         {sifir_sayisi} mamul (fatura verisi yok)")
print("=" * 70)
