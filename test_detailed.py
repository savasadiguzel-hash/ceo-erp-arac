#!/usr/bin/env python3
"""CHZ-V00R00-220001 mamülü detaylı analiz"""

from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi, stok_fiyat_gecmisi

conn = get_connection(
    DB_DEFAULTS['sunucu'],
    DB_DEFAULTS['veritabani'],
    DB_DEFAULTS['kullanici'],
    DB_DEFAULTS['sifre']
)

bom = bom_listesi(conn)
stok = "CHZ-V00R00-220001"

print(f"Mamul: {stok}\n")

# BOM kontrolü
if stok in bom:
    print(f"BOM Bilgisi:")
    print(f"  Ad: {bom[stok]['ad']}")
    print(f"  Bilesenler: {len(bom[stok]['bilesenleri'])}\n")

    for b in bom[stok]['bilesenleri']:
        print(f"  Bileşen: {b['kod']}")
        print(f"    Ad: {b['ad']}")
        print(f"    Miktar: {b['miktar']}")

        # Bu bileşenin fiyat geçmişi
        fiyatlar = stok_fiyat_gecmisi(conn, b['kod'], '01.01.2024', '31.12.2024')
        print(f"    Fiyat Geçmişi: {len(fiyatlar)} kayıt")

        if fiyatlar:
            print(f"      Tarih Aralığı: {fiyatlar[0]['tarih']} - {fiyatlar[-1]['tarih']}")
            total_tutar = sum(f['birim_fiyat'] * f['miktar'] for f in fiyatlar)
            total_miktar = sum(f['miktar'] for f in fiyatlar)
            wa = total_tutar / total_miktar if total_miktar else 0
            print(f"      WA: {wa:.4f} TL")

            # İlk 3 kayıt
            print(f"      Örnekler:")
            for f in fiyatlar[:3]:
                print(f"        {f['tarih']}: {f['birim_fiyat']:.4f} TL x {f['miktar']:.2f}")
        else:
            print(f"      ⚠️  FIYAT GEÇMİŞİ YOK!")

        print()
else:
    print(f"[HATA] {stok} BOM'da bulunamadi!")
