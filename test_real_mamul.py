#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection
from db.sorgular import bom_listesi
from logic.maliyet import mamul_maliyet_hesapla

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

bom = bom_listesi(conn)
print(f"Toplam BOM: {len(bom)} mamul\n")

# En fazla bileşeni olan mamulleri bul
sirali = sorted(bom.items(), key=lambda x: len(x[1]['bilesenleri']), reverse=True)

print("En fazla bileşeni olan ilk 5 mamul:")
for kod, bilgi in sirali[:5]:
    print(f"  {kod} - {bilgi['ad']} ({len(bilgi['bilesenleri'])} bilesen)")

# En fazla bileşenli mamulü test et
if sirali:
    test_kod = sirali[0][0]
    print(f"\n=== {test_kod} maliyet hesaplama ===")
    print("Yontem: WA | Tarih: 01.01.2024 - 31.12.2024\n")

    cache = {}
    satirlar, toplam = mamul_maliyet_hesapla(
        conn, test_kod, 'WA', '01.01.2024', '31.12.2024', _cache=cache
    )

    print(f"Toplam Malzeme Maliyeti: {toplam:.4f} TL")
    print(f"Bilesenler:")
    for s in satirlar:
        print(f"  {s['kod']:<30} miktar={s['bom_miktar']:.2f}  birim_mal={s['birim_mal']:.4f}  satir={s['satir_top']:.4f}")

    if toplam == 0:
        print("\n[UYARI] Maliyet 0 - stok fiyat gecmisi kontrolu yapiliyor...")
        from db.sorgular import stok_fiyat_gecmisi
        for b in bom[test_kod]['bilesenleri'][:3]:
            fiyatlar = stok_fiyat_gecmisi(conn, b['kod'], '01.01.2024', '31.12.2024')
            print(f"  {b['kod']}: {len(fiyatlar)} fiyat kaydi")
