#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

print("=== UretimRecete tablosu (ilk 5 kayit) ===")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT TOP 5 Id, Kodu, Tanim FROM UretimRecete ORDER BY Id")
    for row in cur.fetchall():
        print(f"  Id={row[0]}  Kodu={row[1]}  Tanim={row[2]}")

print("\n=== UretimReceteHatPlani - Tipi degerleri ve sayilari ===")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT Tipi, COUNT(*) as Sayi FROM UretimReceteHatPlani GROUP BY Tipi ORDER BY Tipi")
    for row in cur.fetchall():
        print(f"  Tipi={row[0]}  Sayi={row[1]}")

print("\n=== UretimReceteHatPlani - Tek bir recete ornegi (Id=1) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 10
            urhp.UretimReceteId, urhp.Tipi, urhp.Miktar,
            sk.Kodu as StokKodu, sk.Adi as StokAdi,
            ur.Kodu as ReceteKodu, ur.Tanim as ReceteTanim
        FROM UretimReceteHatPlani urhp
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        LEFT JOIN UretimRecete ur ON ur.Id = urhp.UretimReceteId
        WHERE urhp.UretimReceteId = (SELECT TOP 1 Id FROM UretimRecete)
        ORDER BY urhp.Tipi
    """)
    for row in cur.fetchall():
        print(f"  ReceteId={row[0]}  Tipi={row[1]}  Miktar={row[2]}  StokKodu={row[3]}  ReceteKodu={row[5]}")

print("\n=== Mamul-Bilesen ornegi: GMP-101-230008 ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT
            ur.Kodu as ReceteKodu,
            urhp.Tipi,
            urhp.Miktar,
            sk.Kodu as BilesenKodu,
            sk.Adi as BilesenAdi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'GMP-101-230008'
        ORDER BY urhp.Tipi
    """)
    rows = cur.fetchall()
    if not rows:
        print("  Bulunamadi, basvuru kodlari kontrolu...")
        cur.execute("SELECT TOP 5 Kodu, Tanim FROM UretimRecete ORDER BY Id")
    for row in rows:
        print(f"  ReceteKodu={row[0]}  Tipi={row[1]}  Miktar={row[2]}  BilesenKodu={row[3]}  BilesenAdi={row[4]}")
