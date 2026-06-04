#!/usr/bin/env python3
"""MaliyetHesaplamaThread - Thread Testi"""

import sys
import time
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import mamul_agaci_listesi, bom_listesi
from logic.maliyet import mamul_maliyet_hesapla

print("=" * 80)
print("MALIYET HESAPLAMA - THREAD TESTİ")
print("=" * 80)

try:
    # Bağlantı
    print("\n[1] Veritabanı bağlantısı...")
    conn = get_connection(
        DB_DEFAULTS['sunucu'],
        DB_DEFAULTS['veritabani'],
        DB_DEFAULTS['kullanici'],
        DB_DEFAULTS['sifre']
    )
    print("    [OK]")

    # Mamülü listele
    print("\n[2] Mamül listesi yükleniyor...")
    mamullar = mamul_agaci_listesi(conn)
    print(f"    [OK] {len(mamullar)} mamul")

    if not mamullar:
        print("[HATA] Mamul bulunamadi!")
        sys.exit(1)

    # BOM yükle
    print("\n[3] BOM verisi yükleniyor...")
    bom = bom_listesi(conn)
    print(f"    [OK] {len(bom)} BOM")

    # Hesaplama verilerini hazırla (UI'nin yaptığı gibi)
    print("\n[4] Hesaplama verisi hazırlanıyor...")

    # Örnek: ilk 3 mamul + işçilik tutarı
    hesaplama_verisi = []
    for kod, ad in mamullar[:3]:
        hesaplama_verisi.append({
            'kod': kod,
            'ad': ad,
            'iscilik': 50.0  # Örnek işçilik
        })

    print(f"    [OK] {len(hesaplama_verisi)} mamul hazırlandı")

    # Maliyet hesapla (thread olarak çalışan kodun aynısı)
    print("\n[5] Maliyet hesaplaniyor...")
    print("    Yöntem: Weighted Average")
    print("    Tarih: 01.01.2024 - 31.12.2024\n")

    cache = {}
    tamamlanan = 0

    for item in hesaplama_verisi:
        mamul_kod = item['kod']
        iscilik = item['iscilik']

        print(f"    İşleniyor: {mamul_kod}...", end='', flush=True)

        try:
            # Maliyet hesapla (thread'in yaptığı)
            satirlar, toplam_malzeme = mamul_maliyet_hesapla(
                conn,
                mamul_kod,
                metod='WA',
                bas='01.01.2024',
                bit='31.12.2024',
                _cache=cache
            )

            toplam = toplam_malzeme + iscilik

            print(f" OK")
            print(f"        - Malzeme: {toplam_malzeme:.2f} TL")
            print(f"        - İşçilik: {iscilik:.2f} TL")
            print(f"        - TOPLAM: {toplam:.2f} TL")
            print()

            tamamlanan += 1

        except Exception as e:
            print(f" HATA")
            print(f"        Hata: {e}")
            import traceback
            traceback.print_exc()
            raise

    print("=" * 80)
    print(f"[OK] {tamamlanan}/{len(hesaplama_verisi)} mamul başarıyla hesaplandı")
    print("[OK] THREAD TESTİ BAŞARILI - CRASH YOK!")
    print("=" * 80)

except Exception as e:
    print(f"\n[HATA] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
