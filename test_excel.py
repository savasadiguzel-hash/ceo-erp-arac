#!/usr/bin/env python3
"""Excel cikti testi - tarih formati ve key isimleri"""

import os
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi
from logic.excel import maliyet_excel_kaydet

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

bom = bom_listesi(conn)

# Bilesenleri olan mamulleri sec
secili = [(k, 0.0) for k, v in bom.items() if v['bilesenleri']][:5]

print(f"Test edilecek mamul sayisi: {len(secili)}")
for k, _ in secili:
    print(f"  {k} ({len(bom[k]['bilesenleri'])} bilesen)")

dosya = "C:/yeni-erp/test_cikti.xlsx"

def ilerleme(msg):
    print(f"  -> {msg}")

try:
    maliyet_excel_kaydet(
        dosya, conn, secili,
        metod='WA',
        bas='01.01.2024', bit='31.12.2024',
        bas_g='01.01.2024', bit_g='31.12.2024',
        ilerleme_cb=ilerleme
    )
    size = os.path.getsize(dosya)
    print(f"\n[OK] Excel olusturuldu: {dosya} ({size} bytes)")
except Exception as e:
    print(f"\n[HATA] {e}")
    import traceback
    traceback.print_exc()
