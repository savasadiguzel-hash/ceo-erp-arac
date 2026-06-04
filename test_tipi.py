#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

print("=== MMGMIR61001 reçetesinin TUM bileşenleri (tüm Tipi) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT
            ur.Kodu as ReceteKodu, ur.Tanim as ReceteTanim,
            urhp.Tipi, urhp.Miktar,
            sk.Kodu as BilesenKodu, sk.Adi as BilesenAdi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'MMGMIR61001'
        ORDER BY urhp.Tipi, urhp.Id
    """)
    for row in cur.fetchall():
        print(f"  Tipi={row[2]}  Miktar={row[3]}  Bilesen={row[4]}  BilesenAdi={row[5]}")

print("\n=== GMP-101-230008 reçetesinin TUM bileşenleri ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhp.Tipi, urhp.Miktar, sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'GMP-101-230008'
        ORDER BY urhp.Tipi
    """)
    for row in cur.fetchall():
        print(f"  Tipi={row[0]}  Miktar={row[1]}  BilesenKodu={row[2]}  Adi={row[3]}")

print("\n=== Tipi=2 olan bileşenler (ilk 5 recete) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 15
            ur.Kodu as ReceteKodu, urhp.Tipi, urhp.Miktar,
            sk.Kodu as BilesenKodu, sk.Adi as BilesenAdi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE urhp.Tipi = 2
        ORDER BY ur.Id
    """)
    for row in cur.fetchall():
        print(f"  ReceteKodu={row[0]}  Tipi={row[1]}  Miktar={row[2]}  BilesenKodu={row[3]}")

print("\n=== Tipi=0 olan satirlar ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 5
            ur.Kodu as ReceteKodu, urhp.Tipi, urhp.Miktar,
            sk.Kodu as BilesenKodu, sk.Adi as BilesenAdi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE urhp.Tipi = 0
        ORDER BY ur.Id
    """)
    for row in cur.fetchall():
        print(f"  ReceteKodu={row[0]}  Tipi={row[1]}  Miktar={row[2]}  BilesenKodu={row[3]}")
