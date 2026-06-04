#!/usr/bin/env python3
from config import DB_DEFAULTS
from db.baglanti import get_connection, cursor_ctx

conn = get_connection(DB_DEFAULTS['sunucu'], DB_DEFAULTS['veritabani'],
                      DB_DEFAULTS['kullanici'], DB_DEFAULTS['sifre'])

print("=== UretimRecete tablosu kolonlari ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT COLUMN_NAME, DATA_TYPE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'UretimRecete'
        ORDER BY ORDINAL_POSITION
    """)
    for row in cur.fetchall():
        print(f"  {row[0]:<35} {row[1]}")

print("\n=== UretimRecete - Ilk 3 kayit (tüm kolonlar) ===")
with cursor_ctx(conn) as cur:
    cur.execute("SELECT TOP 3 * FROM UretimRecete ORDER BY Id")
    cols = [d[0] for d in cur.description]
    print("  Kolonlar:", ", ".join(cols))
    for row in cur.fetchall():
        for col, val in zip(cols, row):
            if val is not None and str(val).strip():
                print(f"    {col}: {val}")
        print()

print("=== MMGMIR61001 reçetesinin tüm bileşenleri (Tipi dahil) ===")
with cursor_ctx(conn) as cur:
    cur.execute("""
        SELECT urhp.Id, urhp.Tipi, urhp.Miktar, urhp.KartId,
               sk.Kodu, sk.Adi
        FROM UretimRecete ur
        JOIN UretimReceteHatPlani urhp ON urhp.UretimReceteId = ur.Id
        LEFT JOIN StokKarti sk ON sk.Id = urhp.KartId
        WHERE ur.Kodu = 'MMGMIR61001'
        ORDER BY urhp.Id
    """)
    for row in cur.fetchall():
        print(f"  HatId={row[0]}  Tipi={row[1]}  Miktar={row[2]}  KartId={row[3]}  Kodu={row[4]}  Adi={row[5]}")
