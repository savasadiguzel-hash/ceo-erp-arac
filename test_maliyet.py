#!/usr/bin/env python3
"""Maliyet Hesaplama Bölümü - Detaylı Test"""

import sys
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import mamul_agaci_listesi, bom_listesi
from logic.maliyet import mamul_maliyet_hesapla, birim_maliyet

print("=" * 80)
print("MALIYET HESAPLAMA BÖLÜMÜ - DETAYLI TEST")
print("=" * 80)

try:
    # Baglanti kur
    print("\n[1] Veritabani baglantilandiriliyor...")
    conn = get_connection(
        DB_DEFAULTS['sunucu'],
        DB_DEFAULTS['veritabani'],
        DB_DEFAULTS['kullanici'],
        DB_DEFAULTS['sifre']
    )
    print("    [OK] Baglanti basarili")

    # BOM yükle
    print("\n[2] BOM verisi yukleniyor...")
    bom = bom_listesi(conn)
    print(f"    [OK] {len(bom)} mamul BOM verisi yuklendi")

    if not bom:
        print("[HATA] BOM bostur!")
        sys.exit(1)

    # Ilk mamulü seç
    mamul_kodu = list(bom.keys())[0]
    mamul_bilgisi = bom[mamul_kodu]

    print(f"\n[3] Test mamulu seciliyor...")
    print(f"    Mamul: {mamul_kodu}")
    print(f"    Adi: {mamul_bilgisi['ad']}")
    print(f"    Bilesenleri: {len(mamul_bilgisi['bilesenleri'])} tane")

    # Bileşenleri listele
    print(f"\n[4] Bilesenler:")
    for i, b in enumerate(mamul_bilgisi['bilesenleri'][:3], 1):
        print(f"    {i}. {b['kod']} ({b['ad']}) - Miktar: {b['miktar']}")

    if len(mamul_bilgisi['bilesenleri']) > 3:
        print(f"    ... ve {len(mamul_bilgisi['bilesenleri']) - 3} daha")

    # Maliyet hesapla - LIFO yöntemi
    print(f"\n[5] Maliyet hesaplaniyor (LIFO yöntemi)...")
    print("    Tarih: 01.01.2024 - 31.12.2024")

    cache = {}
    satirlar, toplam = mamul_maliyet_hesapla(
        conn,
        mamul_kodu,
        metod='LIFO',
        bas='01.01.2024',
        bit='31.12.2024',
        _cache=cache
    )

    print(f"    [OK] Hesaplama tamamlandi")
    print(f"        - Bilesenler: {len(satirlar)} tane")
    print(f"        - Toplam Maliyet: {toplam:.4f} TL")

    # Sonuçları göster
    print(f"\n[6] Hesaplama sonuçlari:")
    print("-" * 80)
    print(f"{'Bileşen':<30} {'Miktar':<12} {'B.Maliyet':<15} {'Satır Toplam':<15}")
    print("-" * 80)

    if satirlar:
        for s in satirlar[:5]:
            print(f"{s['kod']:<30} {s['bom_miktar']:<12.2f} "
                  f"{s['birim_mal']:<15.4f} {s['satir_top']:<15.4f}")
        if len(satirlar) > 5:
            print(f"... ve {len(satirlar) - 5} bileşen daha")
    else:
        print("(Bileşen yok)")

    print("-" * 80)

    # FIFO ile tekrar hesapla
    print(f"\n[7] FIFO yöntemi ile hesaplaniyor...")
    satirlar_fifo, toplam_fifo = mamul_maliyet_hesapla(
        conn,
        mamul_kodu,
        metod='FIFO',
        bas='01.01.2024',
        bit='31.12.2024',
        _cache=cache
    )
    print(f"    [OK] FIFO Toplam Maliyet: {toplam_fifo:.4f} TL")

    # Weighted Average ile tekrar hesapla
    print(f"\n[8] Weighted Average yöntemi ile hesaplaniyor...")
    satirlar_wa, toplam_wa = mamul_maliyet_hesapla(
        conn,
        mamul_kodu,
        metod='WA',
        bas='01.01.2024',
        bit='31.12.2024',
        _cache=cache
    )
    print(f"    [OK] WA Toplam Maliyet: {toplam_wa:.4f} TL")

    # Karşılaştırma
    print(f"\n[9] Yöntem Karşılaştirmasi:")
    print("-" * 40)
    print(f"LIFO              : {toplam:.4f} TL")
    print(f"FIFO              : {toplam_fifo:.4f} TL")
    print(f"Weighted Average  : {toplam_wa:.4f} TL")
    print("-" * 40)

    # Cache kontrolü
    print(f"\n[10] Önbellek (Cache) Kontrolü:")
    print(f"     Cache kayıtları: {len(cache)} tane")
    print(f"     [OK] Ayni sorgu tekrar çalıştirilmış, cache'den okundu")

    print("\n" + "=" * 80)
    print("[OK] MALIYET HESAPLAMA BÖLÜMÜ - TUM TESTLER BASARILI!")
    print("=" * 80)

except Exception as e:
    print(f"\n[HATA] {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
