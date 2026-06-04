#!/usr/bin/env python3
"""CEO ERP Araçları - Sistem Testi"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

print("=" * 70)
print("CEO ERP ARAÇLARI - SİSTEM TESTİ")
print("=" * 70)

# Test 1: Import kontrol
print("\n[TEST 1] Modülleri import et...")
try:
    from config import DB_DEFAULTS
    print("  OK - config modülü")

    from db.baglanti import test_baglanti, get_connection
    print("  OK - db.baglanti modülü")

    from db.sorgular import mamul_agaci_listesi, bom_listesi
    print("  OK - db.sorgular modülü")

    from logic.maliyet import mamul_maliyet_hesapla
    print("  OK - logic.maliyet modülü")

    print("[OK] TUM MODULLER BASARILI\n")
except Exception as e:
    print(f"[HATA] IMPORT HATASI: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 2: Config kontrol
print("[TEST 2] Konfigürasyon kontrol...")
print(f"  Sunucu: {DB_DEFAULTS['sunucu']}")
print(f"  Veritabani: {DB_DEFAULTS['veritabani']}")
print(f"  Kullanici: {DB_DEFAULTS['kullanici']}")

if not all([DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'], DB_DEFAULTS['kullanici']]):
    print("[HATA] Eksik konfigurasyon!")
    sys.exit(1)

print("[OK] KONFIGURASYON TAMAM\n")

# Test 3: Bağlantı testi
print("[TEST 3] Veritabani bagi test et...")
ok, msg = test_baglanti(
    DB_DEFAULTS['sunucu'],
    DB_DEFAULTS['veritabani'],
    DB_DEFAULTS['kullanici'],
    DB_DEFAULTS['sifre']
)

if ok:
    print(f"  OK - {msg}")
    print("[OK] BAGLANTI BASARILI\n")
else:
    print(f"  HATA - {msg}")
    print("[HATA] BAGLANTI BASARISIZ\n")
    sys.exit(1)

# Test 4: Canlı veri sorgula
print("[TEST 4] Canli veri sorgula...")
try:
    conn = get_connection(
        DB_DEFAULTS['sunucu'],
        DB_DEFAULTS['veritabani'],
        DB_DEFAULTS['kullanici'],
        DB_DEFAULTS['sifre']
    )

    mamullar = mamul_agaci_listesi(conn)
    print(f"  OK - {len(mamullar)} mamul bulundu")

    if mamullar:
        for i, (kod, ad) in enumerate(mamullar[:3], 1):
            print(f"      {i}. {kod} - {ad}")

    bom = bom_listesi(conn)
    print(f"  OK - {len(bom)} mamul BOM yuklendi")

    print("[OK] CANLI VERI SORGUSU BASARILI\n")
except Exception as e:
    print(f"  HATA - {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("=" * 70)
print("[OK] TUM TESTLER BASARILI - SISTEM HAZIR!")
print("=" * 70)
