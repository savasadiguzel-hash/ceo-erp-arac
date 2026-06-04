#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

# Birden fazla komponenti olan reçeteleri bul
print("=== Birden fazla bileşeni olan reçeteler ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 5 ur.Kodu, ur.Tanim, COUNT(*) as BilesenSayisi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        GROUP BY ur.Id, ur.Kodu, ur.Tanim
        HAVING COUNT(*) > 1
        ORDER BY COUNT(*) DESC
    """)
    receteler = cur.fetchall()
    for row in receteler:
        print(f"  {row[0]}  ({row[2]} bileseni)")

# En fazla bileşeni olan reçetenin detayına bak
if receteler:
    en_buyuk = receteler[0][0]
    print(f"\n=== {en_buyuk} reçetesinin TUM bileşenleri ===")
    with cursor_ctx(conn) as cur:
        cur.execute("""
            SELECT urhp.Id, urhp.Tipi, urhp.Miktar, urhp.KartId,
                   sk.Kodu, sk.Adi
            FROM UretimRecete ur
            JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
            LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
            WHERE ur.Kodu = ?
            ORDER BY urhp.Tipi, urhp.Id
        """, en_buyuk)
        for row in cur.fetchall():
            print(f"  Tipi={row[1]}  Miktar={row[2]}  KartId={row[3]}  StokKodu={row[4]}  Adi={row[5]}")

# Tipi=1 ama farklı stok kodu olanlar (gerçek bileşenler?)
print("\n=== Tipi=1 VE StokKodu != ReceteKodu olan satirlar ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 10
            ur.Kodu as ReceteKodu,
            sk.Kodu as BilesenKodu,
            urhp.Miktar,
            sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE urhp.Tipi = 1
          AND ur.Kodu != sk.Kodu
    """)
    rows = cur.fetchall()
    print(f"  Bulunan: {len(rows)} kayit")
    for row in rows:
        print(f"  Recete={row[0]}  Bilesen={row[1]}  Miktar={row[2]}")

# UretimHareketDetay veya başka bir tablo var mı bileşenler için?
print("\n=== Uretimle ilgili tablolar ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TABLE_NAME
        FROM INFORMATION_SCHEMA.TABLES
        WHERE TABLE_TYPE = 'BASE TABLE'
          AND (TABLE_NAME LIKE '%Uretim%' OR TABLE_NAME LIKE '%BOM%' OR TABLE_NAME LIKE '%Recete%')
        ORDER BY TABLE_NAME
    """)
    for row in cur.fetchall():
        print(f"  {row[0]}")
