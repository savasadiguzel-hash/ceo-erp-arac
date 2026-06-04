#!/usr/bin/env python3

from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi, stok_fiyat_gecmisi

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])
bom = bom_listesi(conn)

stok = "BRSLAKS001"
print(f"Mamul: {stok}\n")

if stok in bom:
    print(f"BOM: {bom[stok]['ad']}")
    print(f"Bilesenler: {len(bom[stok]['bilesenleri'])}\n")

    for b in bom[stok]['bilesenleri'][:3]:
        fiyatlar = stok_fiyat_gecmisi(conn, b['kod'], '01.01.2024', '31.12.2024')
        print(f"{b['kod']}: {len(fiyatlar)} fiyat kaydi")
        if fiyatlar:
            print(f"  Ilk: {fiyatlar[0]['birim_fiyat']:.2f} TL")
            print(f"  Son: {fiyatlar[-1]['birim_fiyat']:.2f} TL")
        print()
else:
    print("BOM'da yok")
