#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

# GMP-200-230602:XX kodlarin recete varligini kontrol et
print("=== GMP-200-230602:XX kodlar UretimRecete'de var mi? ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT ur.Kodu, ur.Tanim
        FROM UretimRecete ur
        WHERE ur.Kodu LIKE 'GMP-200-230602%'
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}  {r[1]}")

# Bu :XX kodlar herhangi bir recetede GIRDI olarak kullaniliyor mu?
print("\n=== GMP-200-230602:XX - herhangi bir recetede girdi mi? ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT ur.Kodu AS ReceteKodu, sk.Kodu AS GirdiKodu, sk.Adi, urhpg.Miktar
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN UretimReceteHatPlaniGirdi urhpg ON urhpg.UretimReceteHatPlaniId = urhp.Id
        JOIN StokKarti sk ON sk.Id = urhpg.KartId
        WHERE sk.Kodu LIKE 'GMP-200-230602:%'
        ORDER BY ur.Kodu, sk.Kodu
    """)
    rows = cur.fetchall()
    print(f"  {len(rows)} satir:")
    for r in rows:
        print(f"  ReceteKodu={r[0]}  GirdiKodu={r[1]}  Adi={r[2][:40]}  Miktar={r[3]}")

# GMP-200-230602:XX kodlarin StokHareket kayitlari var mi? (maliyet icin)
print("\n=== GMP-200-230602:XX fiyat gecmisi (2024) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT sk.Kodu, COUNT(*) as Adet, AVG(CAST(shd.BirimFiyat AS FLOAT)) as OrtFiyat
        FROM StokKarti sk
        JOIN StokHareketDetay shd ON shd.IslemKartId = sk.Id
        JOIN StokHareket sh ON sh.Id = shd.HareketId
        WHERE sk.Kodu LIKE 'GMP-200-230602%'
          AND shd.BirimFiyat > 0
          AND YEAR(sh.BelgeTarihi) = 2024
        GROUP BY sk.Kodu
        ORDER BY sk.Kodu
    """)
    for r in cur.fetchall():
        print(f"  {r[0]}  {r[1]} kayit  Ort={r[2]:.2f} TL")

# GMP-200-230602 nin kendi icin tum UretimReceteHatPlani satirlari
print("\n=== UretimReceteHatPlani - GMP-200-230602'yi iceren TUM receteler ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT ur.Kodu AS ReceteKodu, urhp.Tipi, sk.Kodu AS KartKodu
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE sk.Kodu LIKE 'GMP-200-230602%'
        ORDER BY ur.Kodu
    """)
    for r in cur.fetchall():
        print(f"  ReceteKodu={r[0]}  Tipi={r[1]}  KartKodu={r[2]}")
