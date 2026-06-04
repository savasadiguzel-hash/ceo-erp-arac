#!/usr/bin/env python3
"""GMP-101-230016 reçetesinin tüm satirlarini goster"""

from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

print("=== GMP-101-230016 reçetesinin TUM satirlari ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhp.Id, urhp.Tipi, urhp.Miktar,
               sk.Kodu as StokKodu, sk.Adi as StokAdi,
               ur.Kodu as ReceteKodu
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'GMP-101-230016'
        ORDER BY urhp.Tipi, urhp.Id
    """)
    rows = cur.fetchall()
    if not rows:
        print("  Hic satir yok!")
    for row in rows:
        print(f"  Id={row[0]}  Tipi={row[1]}  Miktar={row[2]}  StokKodu={row[3]}  Adi={row[4]}")

print("\n=== MMGMIR61001 gibi Tipi=1 ile gercek bilesen iceren reçeteler ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 5 ur.Kodu, sk.Kodu as BilesenKodu, sk.Adi, urhp.Tipi, urhp.Miktar
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE urhp.Tipi = 1 AND ur.Kodu != sk.Kodu
    """)
    for row in cur.fetchall():
        print(f"  Recete={row[0]}  Bilesen={row[1]}  Ad={row[2][:30]}  Tipi={row[3]}  Miktar={row[4]}")

print("\n=== GMP-101-230016'nin UretimReceteHatPlaniGirdi tablosunda var mi? ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT TOP 5 * FROM UretimReceteHatPlaniGirdi
        WHERE UretimReceteHatPlaniId IN (
            SELECT urhp.Id
            FROM UretimRecete ur
            JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
            WHERE ur.Kodu = 'GMP-101-230016'
        )
    """)
    rows = cur.fetchall()
    if rows:
        cols = [d[0] for d in cur.description]
        print("  Kolonlar:", cols)
        for row in rows:
            print(f"  {row}")
    else:
        print("  Kayit yok.")
