#!/usr/bin/env python3
"""BOM'da hangi kodlar var, GMP-101-230016 gibi kodlar giriyor mu?"""

from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx
from db.sorgular import bom_listesi

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

bom = bom_listesi(conn)

# GMP-101-230022'nin bilesenleri BOM'da var mi?
kodlar = ["GMP-101-230016", "GMP-101-230033", "GMP-101-230022"]
print("BOM kontrolu:")
for k in kodlar:
    durum = "BOM'DA VAR (alt-mamul)" if k in bom else "BOM'DA YOK (yaprak)"
    print(f"  {k}: {durum}")

print(f"\nBOM'daki 57 anahtardan ilk 20:")
for k in list(bom.keys())[:20]:
    print(f"  {k} - {bom[k]['ad']} ({len(bom[k]['bilesenleri'])} bilesen)")

# Veritabaninda UretimRecete tablosunda var mi?
print("\nUretimRecete'de GMP-101-230016 var mi?")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT Id, Kodu, Tanim FROM UretimRecete WHERE Kodu = ?", "GMP-101-230016")
    row = cur.fetchone()
    if row:
        print(f"  EVET: Id={row[0]}, Kodu={row[1]}, Tanim={row[2]}")
    else:
        print("  HAYIR - Bu kod UretimRecete'de yok, gerçek bir hammadde/parça")

# GMP-101-230016'nin fiyat kaynagi nedir?
print("\nGMP-101-230016'nin fiyat gecmisi (ilk 3 kayit):")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 3
            CONVERT(VARCHAR(10), sh.BelgeTarihi, 120),
            shd.BirimFiyat,
            shd.Miktar,
            sh.IslemKodu
        FROM StokHareketDetay shd
        JOIN StokHareket sh ON sh.Id = shd.HareketId
        JOIN StokKarti sk ON sk.Id = shd.IslemKartId
        WHERE sk.Kodu = 'GMP-101-230016'
          AND shd.BirimFiyat > 0
        ORDER BY sh.BelgeTarihi DESC
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}: {row[1]:.2f} TL x {row[2]:.1f} (IslemKodu={row[3]})")
